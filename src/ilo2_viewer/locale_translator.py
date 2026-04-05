"""Keyboard locale translation for iLO2 remote console.

Translates typed characters into escape sequences for non-US keyboard layouts.
Ported from LocaleTranslator.java.
"""

from __future__ import annotations

import locale as _locale


_EURO1 = " \u20ac\033[+4"
_EURO2 = " \u20ac\033[+e"

_BRITISH = '"@ #\\ @" \\ð |ñ ~| £# ¦\033[+` ¬~ Á\033[+A á\033[+a É\033[+E é\033[+e Í\033[+I í\033[+i Ó\033[+O ó\033[+o Ú\033[+U ú\033[+u'
_BELGIAN = "\001\021 \021\001 \027\032 \032\027 !8 \"3 #\033[+3 $] %\" &1 '4 (5 )- *} +? ,m -= .< /> 0) 1! 2@ 3# 4$ 5% 6^ 7& 8* 9( :. ;, <ð =/ >ñ ?M @\033[+2 AQ M: QA WZ ZW [\033[+[ \\\\\033[+ð ]\033[+] ^[  _+ `\033[+\\\\  aq m; qa wz zw {\033[+9 |\033[+1 }\033[+0 ~\033[+/  £| §6 ¨{  °_ ²` ³~ ´\033[+'  µ\\\\ À\033[+\\\\Q Á\033[+'Q Â[Q Ã\033[+/Q Ä{Q È\033[+\\\\E É\033[+'E Ê[E Ë{E Ì\033[+\\\\I Í\033[+'I Î[I Ï{I Ñ\033[+/N Ò\033[+\\\\O Ó\033[+'O Ô[O Õ\033[+/O Ö{O Ù\033[+\\\\U Ú\033[+'U Û[U Ü{U Ý\033[+'Y à\033[+\\\\q á\033[+'q â[q ã\033[+/q ä{q ç9 è\033[+\\\\e é\033[+'e ê[e ë{e ì\033[+\\\\i í\033[+'i î[i ï{i ñ\033[+/n ò\033[+\\\\o ó\033[+'o ô[o õ\033[+/o ö{o ù\033[+\\\\u ú\033[+'u û[u ü{u ý\033[+'y ÿ{y"
_DANISH = '"@ $\033[+4 &^ \'\\\\ (* )( *| +- -/ /& :> ;< <ð =) >ñ ?_ @\033[+2 [\033[+8 \\\\= ]\033[+9 ^}  _? `+  {\033[+7 |` }\033[+0 ~\033[+]  £\033[+3 ¤$ §~ ¨]  ´=  ½` À+A Á=A Â}A Ã\033[+]A Ä]A Å{ Æ: È+E É=E Ê}E Ë]E Ì+I Í=I Î}I Ï]I Ñ\033[+]N Ò+O Ó=O Ô}O Õ\033[+]O Ö]O Ø" Ù+U Ú=U Û}U Ü]U Ý=Y à+a á=a â}a ã\033[+]a ä]a å[ æ; è+e é=e ê}e ë]e ì+i í=i î}i ï]i ñ\033[+]n ò+o ó=o ô}o õ\033[+]o ö]o ø\' ù+u ú=u û}u ü]u ý=y ÿ]y'
_FINNISH = '"@ $\033[+4 &^ \'\\\\ (* )( *| +- -/ /& :> ;< <ð =) >ñ ?_ @\033[+2 [\033[+8 \\\\\033[+- ]\033[+9 ^}  _? `+  {\033[+7 |\033[+ð }\033[+0 ~\033[+]  £\033[+3 ¤$ §` ¨]  ´=  ½~ À+A Á=A Â}A Ã\033[+]A Ä]A Å{ È+E É=E Ê}E Ë]E Ì+I Í=I Î}I Ï]I Ñ\033[+]N Ò+O Ó=O Ô}O Õ\033[+]O Ö]O Ù+U Ú=U Û}U Ü]U Ý=Y à+a á=a â}a ã\033[+]a ä]a å[ è+e é=e ê}e ë]e ì+i í=i î}i ï]i ñ\033[+]n ò+o ó=o ô}o õ\033[+]o ö]o ù+u ú=u û}u ü]u ý=y ÿ]y'
_FRENCH = "\001\021 \021\001 \027\032 \032\027 !/ \"3 #\033[+3 $] %\" &1 '4 (5 )- *\\\\ ,m -6 .< /> 0) 1! 2@ 3# 4$ 5% 6^ 7& 8* 9( :. ;, <ð >ñ ?M @\033[+0 AQ M: QA WZ ZW [\033[+5 \\\\\033[+8 ]\033[+- ^\033[+9 _8 `\033[+7 aq m; qa wz zw {\033[+4 |\033[+6 }\033[+= ~\033[+2 £} ¤\033[+] §? ¨{  °_ ²` µ| Â[Q Ä{Q Ê[E Ë{E Î[I Ï{I Ô[O Ö{O Û[U Ü{U à0 â[q ä{q ç9 è7 é2 ê[e ë{e î[i ï{i ô[o ö{o ù' û[u ü{u ÿ{y"
_FRENCH_CANADIAN = "\"@ #` '< /# <\\\\ >| ?^ @\033[+2 [\033[+[ \\\\\033[+` ]\033[+] ^[  `'  {\033[+' |~ }\033[+\\\\ ~\033[+; ¢\033[+4 £\033[+3 ¤\033[+5 ¦\033[+7 §\033[+o ¨}  «ð ¬\033[+6 ­\033[+. ¯\033[+, °\033[+ð ±\033[+1 ²\033[+8 ³\033[+9 ´\033[+/  µ\033[+m ¶\033[+p ¸]  »ñ ¼\033[+0 ½\033[+- ¾\033[+= À'A Á\033[+/A Â[A Ä}A Ç]C È'E É? Ê[E Ë}E Ì'I Í\033[+/I Î[I Ï}I Ò'O Ó\033[+/O Ô[O Ö}O Ù'U Ú\033[+/U Û[U Ü}U Ý\033[+/Y à'a á\033[+/a â[a ä}a ç]c è'e é\033[+/e ê[e ë}e ì'i í\033[+/i î[i ï}i ò'o ó\033[+/o ô[o ö}o ù'u ú\033[+/u û[u ü}u ý\033[+/y ÿ}y"
_GERMAN = "\031\032 \032\031 \"@ #\\\\ &^ '| (* )( *} +] -/ /& :> ;< <ð =) >ñ ?_ @\033[+q YZ ZY [\033[+8 \\\\\033[+- ]\033[+9 ^`  _? `+  yz zy {\033[+7 |\033[+ð }\033[+0 ~\033[+] §# °~ ²\033[+2 ³\033[+3 ´=  µ\033[+m À+A Á=A Â`A Ä\" È+E É=E Ê`E Ì+I Í=I Î`I Ò+O Ó=O Ô`O Ö: Ù+U Ú=U Û`U Ü{ Ý=Z ß- à+a á=a â`a ä' è+e é=e ê`e ì+i í=i î`i ò+o ó=o ô`o ö; ù+u ú=u û`u ü[ ý=z"
_ITALIAN = "\"@ #\033[+' &^ '- (* )( *} +] -/ /& :> ;< <ð =) >ñ ?_ @\033[+; [\033[+[ \\\\` ]\033[+] ^+ _? |~ £# §| °\" à' ç: è[ é{ ì= ò; ù\\\\"
_JAPANESE = "\"@ &^ '& (* )( *\" +: :' =_ @[ [] \\\\ò ]\\\\ ^= _ó `{ {} ¥ô |õ }| ~+"
_LATIN_AMERICAN = "\"@ &^ '- (* )( *} +] -/ /& :> ;< <ð =) >ñ ?_ @\033[+q [\" \\\\\033[+- ]| ^\033[+'  _? `\033[+\\\\  {' |` }\\\\ ~\033[+] ¡+ ¨{  ¬\033[+` °~ ´[  ¿= À\033[+\\\\A Á[A Â\033[+'A Ä{A È\033[+\\\\E É[E Ê\033[+'E Ë{E Ì\033[+\\\\I Í[I Î\033[+'I Ï{I Ñ: Ò\033[+\\\\O Ó[O Ô\033[+'O Ö{O Ù\033[+\\\\U Ú[U Û\033[+'U Ü{U Ý[Y à\033[+\\\\a á[a â\033[+'a ä{a è\033[+\\\\e é[e ê\033[+'e ë{e ì\033[+\\\\i í[i î\033[+'i ï{i ñ; ò\033[+\\\\o ó[o ô\033[+'o ö{o ù\033[+\\\\u ú[u û\033[+'u ü{u ý[y ÿ{y"
_NORWEGIAN = '"@ $\033[+4 &^ \'\\\\ (* )( *| +- -/ /& :> ;< <ð =) >ñ ?_ @\033[+2 [\033[+8 \\\\= ]\033[+9 ^}  _? `+  {\033[+7 |` }\033[+0 ~\033[+]  £\033[+3 ¤$ §~ ¨]  ´\033[+=  À+A Á\033[+=A Â}A Ã\033[+]A Ä]A Å{ Æ" È+E É\033[+=E Ê}E Ë]E Ì+I Í\033[+=I Î}I Ï]I Ñ\033[+]N Ò+O Ó\033[+=O Ô}O Õ\033[+]O Ö]O Ø: Ù+U Ú\033[+=U Û}U Ü]U Ý\033[+=Y à+a á\033[+=a â}a ã\033[+]a ä]a å[ æ\' è+e é\033[+=e ê}e ë]e ì+i í\033[+=i î}i ï]i ñ\033[+]n ò+o ó\033[+=o ô}o õ\033[+]o ö]o ø; ù+u ú\033[+=u û}u ü]u ý\033[+=y ÿ]y'
_PORTUGUESE = "\"@ &^ '- (* )( *{ +[ -/ /& :> ;< <ð =) >ñ ?_ @\033[+2 [\033[+8 \\\\` ]\033[+9 ^|  _? `}  {\033[+7 |~ }\033[+0 ~\\\\  £\033[+3 §\033[+4 ¨\033[+[  ª\" «= ´]  º' »+ À}A Á]A Â|A Ã\\\\A Ä\033[+[A Ç: È}E É]E Ê|E Ë\033[+[E Ì}I Í]I Î|I Ï\033[+[I Ñ\\\\N Ò}O Ó]O Ô|O Õ\\\\O Ö\033[+[O Ù}U Ú]U Û|U Ü\033[+[U Ý]Y à}a á]a â|a ã\\\\a ä\033[+[a ç; è}e é]e ê|e ë\033[+[e ì}i í]i î|i ï\033[+[i ñ\\\\n ò}o ó]o ô|o õ\\\\o ö\033[+[o ù}u ú]u û|u ü\033[+[u ý]y ÿ\033[+[y"
_SPANISH = "\"@ #\033[+3 &^ '- (* )( *} +] -/ /& :> ;< <ð =) >ñ ?_ @\033[+2 [\033[+[ \\\\\033[+` ]\033[+] ^{  _? `[  {\033[+' |\033[+1 }\033[+\\\\ ¡= ¨\"  ª~ ¬\033[+6 ´'  ·# º` ¿+ À[A Á'A Â{A Ä\"A Ç| È[E É'E Ê{E Ë\"E Ì[I Í'I Î{I Ï\"I Ñ: Ò[O Ó'O Ô{O Ö\"O Ù[U Ú'U Û{U Ü\"U Ý'Y à[a á'a â{a ä\"a ç\\\\ è[e é'e ê{e ë\"e ì[i í'i î{i ï\"i ñ; ò[o ó'o ô{o ö\"o ù[u ú'u û{u ü\"u ý'y ÿ\"y"
_SWEDISH = '"@ $\033[+4 &^ \'\\\\ (* )( *| +- -/ /& :> ;< <ð =) >ñ ?_ @\033[+2 [\033[+8 \\\\\033[+- ]\033[+9 ^}  _? `+  {\033[+7 |\033[+ð }\033[+0 ~\033[+]  £\033[+3 ¤$ §` ¨]  ´=  ½~ À+A Á=A Â}A Ã\033[+]A Ä]A Å{ È+E É=E Ê}E Ë]E Ì+I Í=I Î}I Ï]I Ñ\033[+]N Ò+O Ó=O Ô}O Õ\033[+]O Ö]O Ù+U Ú=U Û}U Ü]U Ý=Y à+a á=a â}a ã\033[+]a ä]a å[ è+e é=e ê}e ë]e ì+i í=i î}i ï]i ñ\033[+]n ò+o ó=o ô}o õ\033[+]o ö]o ù+u ú=u û}u ü]u ý=y ÿ]y'
_SWISS_FRENCH = "\031\032 \032\031 !} \"@ #\033[+3 $\\\\ &^ '- (* )( *# +! -/ /& :> ;< <ð =) >ñ ?_ @\033[+2 YZ ZY [\033[+[ \\\\\033[+ð ]\033[+] ^=  _? `+  yz zy {\033[+' |\033[+7 }\033[+\\\\ ~\033[+=  ¢\033[+8 £| ¦\033[+1 §` ¨]  ¬\033[+6 °~ ´\033[+-  À+A Á\033[+-A Â=A Ã\033[+=A Ä]A È+E É\033[+-E Ê=E Ë]E Ì+I Í\033[+-I Î=I Ï]I Ñ\033[+=N Ò+O Ó\033[+-O Ô=O Õ\033[+=O Ö]O Ù+U Ú\033[+-U Û=U Ü]U Ý\033[+-Z à+a á\033[+-a â=a ã\033[+=a ä]a ç$ è+e é\033[+-e ê=e ë]e ì+i í\033[+-i î=i ï]i ñ\033[+=n ò+o ó\033[+-o ô=o õ\033[+=o ö]o ù+u ú\033[+-u û=u ü]u ý\033[+-z ÿ]z"
_SWISS_GERMAN = "\031\032 \032\031 !} \"@ #\033[+3 $\\\\ &^ '- (* )( *# +! -/ /& :> ;< <ð =) >ñ ?_ @\033[+2 YZ ZY [\033[+[ \\\\\033[+ð ]\033[+] ^=  _? `+  yz zy {\033[+' |\033[+7 }\033[+\\\\ ~\033[+=  ¢\033[+8 £| ¦\033[+1 §` ¨]  ¬\033[+6 °~ ´\033[+-  À+A Á\033[+-A Â=A Ã\033[+=A Ä]A È+E É\033[+-E Ê=E Ë]E Ì+I Í\033[+-I Î=I Ï]I Ñ\033[+=N Ò+O Ó\033[+-O Ô=O Õ\033[+=O Ö]O Ù+U Ú\033[+-U Û=U Ü]U Ý\033[+-Z à+a á\033[+-a â=a ã\033[+=a ä]a ç$ è+e é\033[+-e ê=e ë]e ì+i í\033[+-i î=i ï]i ñ\033[+=n ò+o ó\033[+-o ô=o õ\033[+=o ö]o ù+u ú\033[+-u û=u ü]u ý\033[+-z ÿ]z"


def _parse_locale_str(s: str) -> dict[str, str]:
    """Parse a locale mapping string into a char -> escape sequence dict."""
    table: dict[str, str] = {}
    state = 0
    key_char = ""
    buf: list[str] = []

    for ch in s:
        if state == 0 and ch != " ":
            state = 1
            key_char = ch
        elif state == 1 and ch != " ":
            if ch == "\xa0":  # non-breaking space maps to regular space
                ch = " "
            buf.append(ch)
        elif state == 1 and ch == " ":
            table[key_char] = "".join(buf)
            state = 0
            buf = []

    if key_char and buf:
        table[key_char] = "".join(buf)

    return table


class LocaleTranslator:
    def __init__(self):
        self._locales: dict[str, dict[str, str]] = {}
        self._aliases: dict[str, str] = {}
        self._reverse_aliases: dict[str, str] = {}
        self._selected: dict[str, str] | None = None
        self._selected_name: str | None = None
        self.show_gui = True

        # en_US has no remapping
        self._locales["en_US"] = {}
        self._aliases["English (United States)"] = "en_US"
        self._reverse_aliases["en_US"] = "English (United States)"

        self._add_locale("en_GB", _BRITISH + _EURO1, "English (United Kingdom)")
        self._add_locale("fr_FR", _FRENCH + _EURO2, "French")
        self._add_locale("it_IT", _ITALIAN + _EURO2, "Italian")
        self._add_locale("de_DE", _GERMAN + _EURO2, "German")
        self._add_locale("es_ES", _SPANISH + _EURO2, "Spanish (Spain)")
        self._add_locale("ja_JP", _JAPANESE, "Japanese")
        self._add_locale("es_MX", _LATIN_AMERICAN + _EURO2, "Spanish (Latin America)")

        for alias in [
            "es_AR", "es_BO", "es_CL", "es_CO", "es_CR", "es_DO", "es_EC",
            "es_GT", "es_HN", "es_NI", "es_PA", "es_PE", "es_PR", "es_PY",
            "es_SV", "es_UY", "es_VE",
        ]:
            self._locales[alias] = self._locales["es_MX"]
            self._reverse_aliases[alias] = self._reverse_aliases["es_MX"]

        self._add_locale("fr_BE", _BELGIAN + _EURO2, "French Belgium")
        self._add_locale("fr_CA", _FRENCH_CANADIAN + _EURO2, "French Canadian")
        self._add_locale("da_DK", _DANISH + _EURO2, "Danish")
        self._add_locale("no_NO", _NORWEGIAN + _EURO2, "Norwegian")
        self._add_locale("pt_PT", _PORTUGUESE + _EURO2, "Portugese")
        self._add_locale("sv_SE", _SWEDISH + _EURO2, "Swedish")
        self._add_locale("fi_FI", _FINNISH + _EURO2, "Finnish")
        self._add_locale("fr_CH", _SWISS_FRENCH + _EURO2, "Swiss (French)")
        self._add_locale("de_CH", _SWISS_GERMAN + _EURO2, "Swiss (German)")

        # Try to auto-select based on system locale
        sys_locale = _locale.getdefaultlocale()[0] or "en_US"
        self.select_locale(sys_locale)

    def _add_locale(self, iso_code: str, mapping_str: str, display_name: str):
        table = _parse_locale_str(mapping_str)
        self._locales[iso_code] = table
        self._aliases[display_name] = iso_code
        self._reverse_aliases[iso_code] = display_name

    def select_locale(self, name: str) -> bool:
        iso = self._aliases.get(name, name)
        table = self._locales.get(iso)
        if table is not None:
            self._selected = table
            self._selected_name = self._reverse_aliases.get(iso)
            return True
        return False

    def translate(self, char: str) -> str:
        if self._selected and char in self._selected:
            return self._selected[char]
        return char

    def get_locales(self) -> list[str]:
        return sorted(self._aliases.keys())

    def get_selected(self) -> str | None:
        return self._selected_name
