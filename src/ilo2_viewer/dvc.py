"""DVC (Display/Video Compression) decoder for iLO2 remote console.

Ported from cim.java - implements the 48-state Huffman-like video decoder
that processes the proprietary HP iLO2 DVC video stream into 16x16 pixel blocks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .display import DisplayWidget

# State constants
RESET = 0; START = 1; PIXELS = 2; PIXLRU1 = 3; PIXLRU0 = 4
PIXCODE1 = 5; PIXCODE2 = 6; PIXCODE3 = 7; PIXGREY = 8; PIXRGBR = 9
PIXRPT = 10; PIXRPT1 = 11; PIXRPTSTD1 = 12; PIXRPTSTD2 = 13; PIXRPTNSTD = 14
CMD = 15; CMD0 = 16; MOVEXY0 = 17; EXTCMD = 18; CMDX = 19
MOVESHORTX = 20; MOVELONGX = 21; BLKRPT = 22; EXTCMD1 = 23; FIRMWARE = 24
EXTCMD2 = 25; MODE0 = 26; TIMEOUT = 27; BLKRPT1 = 28; BLKRPTSTD = 29
BLKRPTNSTD = 30; PIXFAN = 31; PIXCODE4 = 32; PIXDUP = 33; BLKDUP = 34
PIXCODE = 35; PIXSPEC = 36; EXIT = 37; LATCHED = 38; MOVEXY1 = 39
MODE1 = 40; PIXRGBG = 41; PIXRGBB = 42; HUNT = 43; PRINT0 = 44
PRINT1 = 45; CORP = 46; MODE2 = 47; SIZE_OF_ALL = 48

BITS_TO_READ = [
    0, 1, 1, 1, 1, 1, 2, 3,
    4, 4, 1, 1, 3, 3, 8, 1,
    1, 7, 1, 1, 3, 7, 1, 1,
    8, 1, 7, 0, 1, 3, 7, 1,
    4, 0, 0, 0, 1, 0, 1, 7,
    7, 4, 4, 1, 8, 8, 1, 4,
]

NEXT_0 = [
    1, 2, 31, 2, 2, 10, 10, 10,
    10, 41, 2, 33, 2, 2, 2, 16,
    19, 39, 22, 20, 1, 1, 34, 25,
    46, 26, 40, 1, 29, 1, 1, 36,
    10, 2, 1, 35, 8, 37, 38, 1,
    47, 42, 10, 43, 45, 45, 1, 1,
]

NEXT_1 = [
    1, 15, 3, 11, 11, 10, 10, 10,
    10, 41, 11, 12, 2, 2, 2, 17,
    18, 39, 23, 21, 1, 1, 28, 24,
    46, 27, 40, 1, 30, 1, 1, 35,
    10, 2, 1, 35, 9, 37, 38, 1,
    47, 42, 10, 0, 45, 45, 24, 1,
]

GETMASK = [0x0, 0x1, 0x3, 0x7, 0xF, 0x1F, 0x3F, 0x7F, 0xFF]


class DVCDecoder:
    """Decodes the iLO2 DVC video stream into pixel blocks."""

    def __init__(self, screen: DisplayWidget):
        self.screen = screen
        self._next_1 = list(NEXT_1)  # mutable copy since pixcode updates slot 31

        # Reversal tables
        self._reversal = [0] * 256
        self._left = [0] * 256
        self._right = [0] * 256
        self._initialized = False

        # Color cache (LRU, up to 17 entries)
        self._cc_active = 0
        self._cc_color = [0] * 17
        self._cc_usage = [0] * 17
        self._cc_block = [0] * 17

        # Decoder state
        self._pixel_count = 0
        self._size_x = 0
        self._size_y = 0
        self._y_clipped = 0
        self._lastx = 0
        self._lasty = 0
        self._newx = 0
        self._newy = 0
        self._color = 0
        self._last_color = 0
        self._ib_acc = 0
        self._ib_bcnt = 0
        self._zero_count = 0
        self._decoder_state = RESET
        self._next_state = RESET
        self._pixcode = LATCHED
        self._code = 0
        self._block = [0] * 256
        self._red = 0
        self._green = 0
        self._blue = 0

        self._fatal_count = 0
        self._printchan = 0
        self._printstring = ""
        self._count_bytes = 0
        self._cmd_p_buff = [0] * 256
        self._cmd_p_count = 0
        self._cmd_last = 0
        self._framerate = 30
        self._debug = False
        self._timeout_count = 0
        self._process_inhibit = False
        self._video_detected = True

        # Color remap table: 12-bit -> 24-bit
        self._color_remap = [0] * 4096

        # Callbacks (set by connection layer)
        self.on_change_key: callable = lambda: None
        self.on_seize: callable = lambda: None
        self.on_start_rdp: callable = lambda ts_type: None
        self.on_stop_rdp: callable = lambda: None
        self.on_refresh_screen: callable = lambda: None
        self.on_set_status: callable = lambda field, msg: None

        # Screen dimensions (reported to mouse sync)
        self.screen_x = 1
        self.screen_y = 1

    def _init_reversal(self):
        for i in range(256):
            first_one = 8
            last_one = 8
            k = i
            m = 0
            for j in range(8):
                m <<= 1
                if k & 1:
                    if first_one > j:
                        first_one = j
                    m |= 1
                    last_one = 7 - j
                k >>= 1
            self._reversal[i] = m
            self._right[i] = first_one
            self._left[i] = last_one

    def _init_color_remap(self):
        for j in range(4096):
            self._color_remap[j] = (
                (j & 0xF00) * 0x1100
                + (j & 0xF0) * 0x110
                + (j & 0xF) * 0x11
            )

    # Color cache methods
    def _cache_reset(self):
        self._cc_active = 0

    def _cache_lru(self, color: int) -> int:
        """Add/promote color in LRU cache. Returns 1 if already present, 0 if new."""
        k = self._cc_active
        j = 0
        found = False

        for i in range(k):
            if color == self._cc_color[i]:
                j = i
                found = True
                break
            if self._cc_usage[i] == k - 1:
                j = i

        m = self._cc_usage[j]

        if not found:
            if k < 17:
                j = k
                m = k
                k += 1
                self._cc_active = k
                self._update_pixcode()
            self._cc_color[j] = color

        self._cc_block[j] = 1

        for i in range(k):
            if self._cc_usage[i] < m:
                self._cc_usage[i] += 1
        self._cc_usage[j] = 0
        return 1 if found else 0

    def _cache_find(self, usage_rank: int) -> int:
        """Find color by usage rank. Returns color or -1."""
        active = self._cc_active
        for j in range(active):
            if usage_rank == self._cc_usage[j]:
                color = self._cc_color[j]
                k = j
                for jj in range(active):
                    if self._cc_usage[jj] < usage_rank:
                        self._cc_usage[jj] += 1
                self._cc_usage[k] = 0
                self._cc_block[k] = 1
                return color
        return -1

    def _cache_prune(self):
        j = self._cc_active
        i = 0
        while i < j:
            if self._cc_block[i] == 0:
                j -= 1
                self._cc_block[i] = self._cc_block[j]
                self._cc_color[i] = self._cc_color[j]
                self._cc_usage[i] = self._cc_usage[j]
            else:
                self._cc_block[i] -= 1
                i += 1
        self._cc_active = j
        self._update_pixcode()

    def _update_pixcode(self):
        if self._cc_active < 2:
            self._pixcode = LATCHED
        elif self._cc_active == 2:
            self._pixcode = PIXLRU0
        elif self._cc_active == 3:
            self._pixcode = PIXCODE1
        elif self._cc_active < 6:
            self._pixcode = PIXCODE2
        elif self._cc_active < 10:
            self._pixcode = PIXCODE3
        else:
            self._pixcode = PIXCODE4
        self._next_1[31] = self._pixcode

    def _next_block(self, count: int):
        show = self._video_detected

        if self._pixel_count != 0:
            if self._y_clipped > 0 and self._lasty == self._size_y:
                fill_color = self._color_remap[0]
                for j in range(self._y_clipped, 256):
                    self._block[j] = fill_color

        self._pixel_count = 0
        self._next_state = START

        x = self._lastx * 16
        y = self._lasty * 16
        while count != 0:
            if show:
                self.screen.paste_block(x, y, self._block, 16)
            self._lastx += 1
            x += 16
            if self._lastx >= self._size_x:
                break
            count -= 1

    def _add_bits(self, byte_val: int) -> int:
        self._zero_count += self._right[byte_val]
        self._ib_acc |= byte_val << self._ib_bcnt
        self._ib_bcnt += 8

        if self._zero_count > 30:
            self._next_state = HUNT
            self._decoder_state = HUNT
            return 4

        if byte_val != 0:
            self._zero_count = self._left[byte_val]
        return 0

    def _get_bits(self, n: int) -> int:
        if n == 1:
            self._code = self._ib_acc & 1
            self._ib_acc >>= 1
            self._ib_bcnt -= 1
            return 0
        if n == 0:
            return 0

        val = self._ib_acc & GETMASK[n]
        self._ib_bcnt -= n
        self._ib_acc >>= n
        val = self._reversal[val]
        val >>= 8 - n
        self._code = val
        return 0

    def process_dvc(self, byte_val: int) -> bool:
        """Process one byte of DVC data. Returns True to stay in DVC mode."""
        if not self._initialized:
            self._initialized = True
            self._init_reversal()
            self._cache_reset()
            self._decoder_state = RESET
            self._next_state = RESET
            self._zero_count = 0
            self._ib_acc = 0
            self._ib_bcnt = 0
            self._init_color_remap()

        if not self._process_inhibit:
            result = self._process_bits(byte_val)
        else:
            result = 0

        if result == 0:
            return True
        else:
            print(f"Exit from DVC mode status={result}")
            self._decoder_state = LATCHED
            self._next_state = LATCHED
            self._fatal_count = 0
            self.on_refresh_screen()
            return True

    def _process_bits(self, byte_val: int) -> int:
        self._add_bits(byte_val)
        self._count_bytes += 1
        m = 0

        while m == 0:
            k = BITS_TO_READ[self._decoder_state]
            if k > self._ib_bcnt:
                break

            self._get_bits(k)

            if self._code == 0:
                self._next_state = NEXT_0[self._decoder_state]
            else:
                self._next_state = self._next_1[self._decoder_state]

            state = self._decoder_state

            # ---- Pixel LRU / Code states ----
            if state in (PIXLRU1, PIXLRU0, PIXCODE1, PIXCODE2, PIXCODE3, PIXCODE4):
                if self._cc_active == 1:
                    self._code = self._cc_usage[0]
                elif state == PIXLRU0:
                    self._code = 0
                elif state == PIXLRU1:
                    self._code = 1
                elif self._code != 0:
                    self._code += 1

                self._color = self._cache_find(self._code)
                if self._color == -1:
                    self._next_state = LATCHED
                else:
                    self._last_color = self._color_remap[self._color]
                    if self._pixel_count < 256:
                        self._block[self._pixel_count] = self._last_color
                    else:
                        self._next_state = LATCHED
                        break
                    self._pixel_count += 1

            # ---- Pixel repeat std 1 ----
            elif state == PIXRPTSTD1:
                if self._code == 7:
                    self._next_state = PIXRPTNSTD
                elif self._code == 6:
                    self._next_state = PIXRPTSTD2
                else:
                    count = self._code + 2
                    for _ in range(count):
                        if self._pixel_count < 256:
                            self._block[self._pixel_count] = self._last_color
                        else:
                            self._next_state = LATCHED
                            break
                        self._pixel_count += 1

            # ---- Pixel repeat std 2 ----
            elif state == PIXRPTSTD2:
                self._code += 8
                # fall through to PIXRPTNSTD logic
                for _ in range(self._code):
                    if self._pixel_count < 256:
                        self._block[self._pixel_count] = self._last_color
                    else:
                        self._next_state = LATCHED
                        break
                    self._pixel_count += 1

            # ---- Pixel repeat non-std ----
            elif state == PIXRPTNSTD:
                for _ in range(self._code):
                    if self._pixel_count < 256:
                        self._block[self._pixel_count] = self._last_color
                    else:
                        self._next_state = LATCHED
                        break
                    self._pixel_count += 1

            # ---- Pixel duplicate ----
            elif state == PIXDUP:
                if self._pixel_count < 256:
                    self._block[self._pixel_count] = self._last_color
                else:
                    self._next_state = LATCHED
                    break
                self._pixel_count += 1

            # ---- No-op states ----
            elif state in (START, PIXELS, PIXRPT, PIXRPT1, BLKRPT, BLKRPT1, PIXFAN, PIXSPEC):
                pass

            # ---- Pixel code redirect ----
            elif state == PIXCODE:
                self._next_state = self._pixcode

            # ---- RGB red ----
            elif state == PIXRGBR:
                self._red = self._code << 8

            # ---- RGB green ----
            elif state == PIXRGBG:
                self._green = self._code << 4

            # ---- Grey / RGB blue ----
            elif state == PIXGREY:
                self._red = self._code << 8
                self._green = self._code << 4
                # fall through to blue
                self._blue = self._code
                self._color = self._red | self._green | self._blue
                hit = self._cache_lru(self._color)
                if hit != 0:
                    self._next_state = LATCHED
                else:
                    self._last_color = self._color_remap[self._color]
                    if self._pixel_count < 256:
                        self._block[self._pixel_count] = self._last_color
                    else:
                        self._next_state = LATCHED
                        break
                    self._pixel_count += 1

            elif state == PIXRGBB:
                self._blue = self._code
                self._color = self._red | self._green | self._blue
                hit = self._cache_lru(self._color)
                if hit != 0:
                    self._next_state = LATCHED
                else:
                    self._last_color = self._color_remap[self._color]
                    if self._pixel_count < 256:
                        self._block[self._pixel_count] = self._last_color
                    else:
                        self._next_state = LATCHED
                        break
                    self._pixel_count += 1

            # ---- Move XY ----
            elif state in (MOVEXY0, MODE0):
                self._newx = self._code
                if state == MOVEXY0 and self._newx > self._size_x:
                    self._newx = 0

            elif state == MOVEXY1:
                self._newy = self._code & 0x7F
                self._lastx = self._newx
                self._lasty = self._newy
                if self._lasty > self._size_y:
                    self._lasty = 0
                self.screen.mark_dirty()

            # ---- Move short X ----
            elif state == MOVESHORTX:
                self._code = self._lastx + self._code + 1
                if self._code > self._size_x:
                    pass
                self._lastx = self._code & 0x7F
                if self._lastx > self._size_x:
                    self._lastx = 0

            # ---- Move long X ----
            elif state == MOVELONGX:
                self._lastx = self._code & 0x7F
                if self._lastx > self._size_x:
                    self._lastx = 0

            # ---- Timeout ----
            elif state == TIMEOUT:
                if self._timeout_count == self._count_bytes - 1:
                    self._next_state = LATCHED

                if self._ib_bcnt & 7:
                    self._get_bits(self._ib_bcnt & 7)
                self._timeout_count = self._count_bytes
                self.screen.mark_dirty()

            # ---- Firmware command accumulator ----
            elif state == FIRMWARE:
                if self._cmd_p_count != 0:
                    self._cmd_p_buff[self._cmd_p_count - 1] = self._cmd_last
                self._cmd_p_count += 1
                self._cmd_last = self._code

            # ---- Corp (firmware command terminator) ----
            elif state == CORP:
                if self._code == 0:
                    cmd = self._cmd_last
                    if cmd == 1:  # EXIT
                        self._next_state = EXIT
                    elif cmd == 2:  # PRINT
                        self._next_state = PRINT0
                    elif cmd == 3:  # FRAMERATE
                        if self._cmd_p_count != 0:
                            self._framerate = self._cmd_p_buff[0]
                            self.screen.set_framerate(self._cmd_p_buff[0])
                        else:
                            self.screen.set_framerate(0)
                        self.on_set_status(3, str(self._framerate))
                    elif cmd == 6:  # VIDEO SUSPENDED
                        self.screen.show_text("Video suspended")
                        self.on_set_status(2, "Video_suspended")
                        self.screen_x = 640
                        self.screen_y = 100
                    elif cmd == 7:  # START RDP
                        self.on_start_rdp(self._cmd_p_buff[0])
                    elif cmd == 8:  # STOP RDP
                        self.on_stop_rdp()
                    elif cmd == 9:  # CHANGE KEY
                        if self._ib_bcnt & 7:
                            self._get_bits(self._ib_bcnt & 7)
                        self.on_change_key()
                    elif cmd == 10:  # SEIZE
                        self.on_seize()

                    self._cmd_p_count = 0

            # ---- Print ----
            elif state == PRINT0:
                self._printchan = self._code
                self._printstring = ""

            elif state == PRINT1:
                if self._code != 0:
                    self._printstring += chr(self._code)
                else:
                    chan = self._printchan
                    if chan in (1, 2):
                        self.on_set_status(2 + chan, self._printstring)
                    elif chan == 3:
                        print(self._printstring)
                    elif chan == 4:
                        self.screen.show_text(self._printstring)
                    self._next_state = START

            # ---- Navigation states (no-op) ----
            elif state in (CMD, CMD0, EXTCMD, CMDX, EXTCMD1, EXTCMD2):
                pass

            # ---- Reset ----
            elif state == RESET:
                self._cache_reset()
                self._pixel_count = 0
                self._lastx = 0
                self._lasty = 0
                self._red = 0
                self._green = 0
                self._blue = 0
                self._fatal_count = 0
                self._timeout_count = -1
                self._cmd_p_count = 0

            # ---- Latched (error recovery) ----
            elif state == LATCHED:
                self._fatal_count += 1
                if self._fatal_count == 11680:
                    self.on_refresh_screen()
                if self._fatal_count == 120000:
                    self.on_refresh_screen()
                if self._fatal_count >= 12000000:
                    self.on_refresh_screen()
                    self._fatal_count = 41

            # ---- Block duplicate ----
            elif state == BLKDUP:
                self._next_block(1)

            # ---- Block repeat std ----
            elif state == BLKRPTSTD:
                self._code += 2
                self._next_block(self._code)

            # ---- Block repeat non-std ----
            elif state == BLKRPTNSTD:
                self._next_block(self._code)

            # ---- Mode 1 (set screen size) ----
            elif state == MODE1:
                self._size_x = self._newx
                self._size_y = self._code

            # ---- Mode 2 (apply screen dimensions) ----
            elif state == MODE2:
                self._lastx = 0
                self._lasty = 0
                self._pixel_count = 0
                self._cache_reset()
                self.screen_x = self._size_x * 16
                self.screen_y = self._size_y * 16 + self._code

                if self.screen_x == 0 or self.screen_y == 0:
                    self._video_detected = False
                else:
                    self._video_detected = True

                if self._code > 0:
                    self._y_clipped = 256 - 16 * self._code
                else:
                    self._y_clipped = 0

                if not self._video_detected:
                    self.screen.show_text("No Video")
                    self.on_set_status(2, "No Video")
                    self.screen_x = 640
                    self.screen_y = 100
                else:
                    self.screen.set_dimensions(self.screen_x, self.screen_y)
                    self.on_set_status(2, f" Video:{self.screen_x}x{self.screen_y}")

            # ---- Hunt (reset detection) ----
            elif state == HUNT:
                if self._next_state != state:
                    self._ib_bcnt = 0
                    self._ib_acc = 0
                    self._zero_count = 0
                    self._count_bytes = 0

            # ---- Exit ----
            elif state == EXIT:
                return 1

            # ---- Block completion check ----
            if self._next_state == PIXELS and self._pixel_count == 256:
                self._next_block(1)
                self._cache_prune()

            # ---- Hung state detection ----
            if (self._decoder_state == self._next_state
                    and state != PRINT1
                    and state != LATCHED
                    and state != HUNT):
                print(f"Machine hung in state {state}")
                m = 6
            else:
                self._decoder_state = self._next_state

        return m
