"""Editorial family taxonomy. A technical family identifies hardware, not truth."""
import re
from functools import lru_cache
from urllib.parse import urlsplit

from ..catalog_display import description_text
from ..history_sources import maker_aliases, model_names, model_key
from .identity import maker_key, manufacturer_base


@lru_cache(maxsize=512)
def maker_identity(value):
    key = maker_key(maker_aliases(manufacturer_base(value))[0])
    return 'tandy' if key in ('radio shack', 'radioshack', 'tandy radio shack', 'tandy') else key


# Specific models precede family fallbacks: a PC-compatible portable is still
# classified Portable, and a Kaypro logic analyzer is not a Kaypro computer.
EXTRA_RULES = (
    ('Apple', r'^(?:(?:Macintosh )?PowerBook|iBook|MacBook)(?:\s|\d|Pro\b|Air\b|$)|^(?:Macintosh )?Portable\b', 'Portable'),
    ('Acorn', r'^(?:Acorn )?A3010$', 'Home computer'),
    ('Acorn', r'^(?:Acorn )?(?:Atom|Electron)\b', 'Home computer'),
    ('Acorn', r'^(?:Acorn )?(?:A3020|A4000|A5000|ABC 110|ABC 310|Communicator)\b', 'Personal computer'),
    ('Acorn', r'^(?:Acorn )?(?:A4|Briefcase Communicator)$', 'Portable'),
    ('Acorn', r'^(?:Acorn )?System [1-5]$', 'Microcomputer'),
    ('Acorn Computers / Slogger', r'^Acorn Electron\b', 'Home computer'),
    ('Commodore', r'^(?:SX-64|DX-64|Executive 64)', 'Portable'),
    ('Commodore', r'^(?:B128|B256|B500|BX256|P500|MicroMainFrame 9000)\b', 'Personal computer'),
    ('Commodore', r'^(?:Educator 64|VIP-64)\b', 'Home computer'),
    ('IBM', r'^(?:IBM )?(?:5100|5110)\b', 'Portable'),
    ('IBM', r'^RS/6000.*\bServer\b', 'Server'),
    ('IBM', r'^(?:IBM )?6580\b', 'Personal computer'),
    ('Cray Research', r'^Cray[- ]?(?:1|2|X-MP|Y-MP)\b', 'Supercomputer'),
    ('DEC', r'^DEC 2000 Model 500 AXP\b', 'Server'),
    ('DEC', r'^(?:DEC 2000 Model 300 AXP|DECpc AXP 150)\b', 'Workstation'),
    ('DEC', r'^DECmate (?:II|III)\b', 'Personal computer'),
    ('Sun', r'^Ultra 45\b', 'Workstation'),
    ('NeXT', r'^(?:NeXT\s*Computer|NeXTcube|NeXTstation|cube|station)\b', 'Workstation'),
    ('Silicon Graphics', r'^(?:IRIS|Personal IRIS|Professional IRIS|Indigo2?|Indy|Crimson|Octane|O2)\b', 'Workstation'),
    ('Sony', r'^(?:NET WORK STATION|NWS[- ])', 'Workstation'),
    ('Sony', r'^SMC-777\b', 'Home computer'),
    ('HP', r'^(?:HP\s*)?(?:85|86B|87|98(?:25|30|31|35|45)[A-Z]?)\b', 'Personal computer'),
    ('HP', r'^(?:HP\s*)?(?:9816|9826|9836|9000/3)', 'Workstation'),
    ('HP', r'^Integral Personal Computer\b', 'Portable'),
    ('Atari', r'^TT030\b', 'Workstation'),
    ('Atari', r'^(?:Portfolio)$', 'Portable'),
    ('Atari', r'^(?:Falcon030|MEGA ST|MEGA STe|STe?|800XE|XE Game System)\b', 'Home computer'),
    ('Atari', r'^PC[13]$', 'Personal computer'),
    ('Amstrad', r'^(?:PPC(?:512|640)|NC(?:100|150|200)|PenPad PDA 600)\b', 'Portable'),
    ('Amstrad', r'^(?:CPC|ZX Spectrum)', 'Home computer'),
    ('Amstrad', r'^PC(?:20|2086|3086|5086)\b', 'Personal computer'),
    ('Sinclair', r'^ZX[- ]?(?:80|81|Spectrum)\b', 'Home computer'),
    ('Sinclair', r'^(?:QL|PC200)\b', 'Personal computer'),
    ('Fujitsu', r'^FM[- ]?(?:7\b|77|NEW7)', 'Home computer'),
    ('Fujitsu', r'^FM[- ]?(?:8\b|11\b|Towns)', 'Personal computer'),
    ('Kaypro', r'^(?:PC|Kaypro Robie)$', 'Personal computer'),
    ('Kaypro', r'^Kaypro (?:[124]|10|16|New 2)', 'Portable'),
    ('Non-Linear Systems', r'^Kaypro (?:10|II|IV)\b', 'Portable'),
    ('Epson', r'^(?:Epson )?(?:HX-20|PX-[48]|CM60|CM61)', 'Portable'),
    ('Epson', r'^(?:PC-[234]|QX-10)', 'Personal computer'),
    ('Tandy', r'^TRS-80 Model 4P\b', 'Portable'),
    ('Tandy', r'^(?:Color Computer|Deluxe Color Computer|MC-10|TRS-80 Model (?:I|III)\b)', 'Home computer'),
    ('Tandy', r'^(?:Tandy [12]000|TRS-80 Model (?:II|4|16)\b)', 'Personal computer'),
    ('NEC', r'^(?:PC-8[45]0|PC-98(?:HA|LT))', 'Portable'),
    ('NEC', r'^EWS4800\b', 'Workstation'),
    ('NEC', r'^(?:APC|PC-100)\b', 'Personal computer'),
    ('Olivetti', r'^(?:M15|M21)\b', 'Portable'),
    ('Olivetti', r'^(?:(?:Olivetti )?L1 M20|M24|M240)\b', 'Personal computer'),
    ('Olivetti', r'^Prodest PC (?:1|128S?)\b', 'Home computer'),
    ('Philips', r'^(?:Philips )?P2000M\b|^(?::YES|NMS 9100)\b', 'Personal computer'),
    ('Philips', r'^(?:Philips )?P2000T\b|^VG-5000\b', 'Home computer'),
    ('Sharp', r'^(?:PC-7000\b|PC-[EG](?=\d)|Pocket Computer\b|Zaurus\b)', 'Portable'),
    ('Sharp', r'^MZ-(?:80|2000|2200|2500|2520|3500|6500)', 'Personal computer'),
    ('Compaq', r'^Compaq Portable\b', 'Portable'),
    ('Compaq', r'^Deskpro\b', 'Personal computer'),
    ('Data General', r'^(?:Data General/)?One$', 'Portable'),
    ('Cambridge Computers', r'^Z88\b', 'Portable'),
    ('EACA', r'^(?:System-80|Video Genie)\b', 'Home computer'),
    ('Intelligent Software / Enterprise Computers', r'^Enterprise (?:One Two Eight|Sixty Four|64|128)\b', 'Home computer'),
)

FAMILIES = {
    'Home computer': '''apple/apple2.cpp apple/apple2e.cpp apple/tk2000.cpp
        sinclair/spectrum.cpp sinclair/zx.cpp sinclair/spec128.cpp sinclair/specpls3.cpp
        sinclair/scorpion.cpp sinclair/atm.cpp sinclair/pentagon.cpp sinclair/timex.cpp
        sinclair/byte.cpp sinclair/elwro800.cpp sinclair/sprinter.cpp sinclair/specnext.cpp
        thomson/thomson.cpp trs/coco12.cpp trs/coco3.cpp trs/dragon.cpp trs/mc10.cpp
        trs/trs80.cpp trs/meritum.cpp trs/radionic.cpp trs/lnw80.cpp trs/max80.cpp
        amstrad/amstrad.cpp atari/atarist.cpp atari/atari400.cpp commodore/c64.cpp
        camputers/camplynx.cpp enterprise/ep64.cpp memotech/mtx.cpp
        tangerine/oric.cpp philips/p2000t.cpp philips/vg5k.cpp
        sanyo/phc20.cpp sanyo/phc25.cpp svi/svi318.cpp tatung/einstein.cpp
        toshiba/pasopia7.cpp toshiba/pasopia.cpp sony/smc777.cpp sord/m5.cpp olivetti/olivpc1.cpp'''.split(),
    'Personal computer': '''pc/pc.cpp pc/tandy1t.cpp pc/europc.cpp trs/tandy2k.cpp
        trs/trs80m2.cpp trs/trs80m3.cpp fujitsu/fmtowns.cpp hp/hp9845.cpp hp/hp9825.cpp hp/hp80.cpp
        heathzenith/h89.cpp heathzenith/z100.cpp morrow/microdec.cpp epson/qx10.cpp
        nec/apc.cpp nec/pc100.cpp nec/pc9801_epson.cpp olivetti/m24.cpp apple/mac128.cpp toshiba/paso1600.cpp
        dec/decmate2.cpp sanyo/mbc200.cpp sanyo/mbc55x.cpp sharp/mz2000.cpp
        sharp/mz2500.cpp sharp/mz80.cpp sharp/mz3500.cpp sharp/mz6500.cpp
        tangerine/hhtiger.cpp sinclair/ql.cpp commodore/pet.cpp commodore/cbm2.cpp acorn/accomm.cpp'''.split(),
    'Portable': '''sharp/pocketc.cpp sharp/pce220.cpp sharp/pc1500.cpp sharp/zaurus.cpp
        acorn/z88.cpp atari/pofo.cpp amstrad/nc.cpp amstrad/pda600.cpp
        epson/hx20.cpp epson/px4.cpp epson/px8.cpp nec/pc8401a.cpp nec/pc98ha.cpp
        hp/hp_ipc.cpp ibm/ibm5100.cpp osborne/osborne1.cpp osborne/osbexec.cpp osborne/vixen.cpp
        pc/tosh1000.cpp kaypro/kaypro.cpp'''.split(),
    'Workstation': '''next/next.cpp sgi/indy_indigo2.cpp sgi/ip12.cpp sgi/ip20.cpp
        sgi/ip6.cpp sgi/tt.cpp sgi/crimson.cpp sgi/iris3130.cpp sgi/octane.cpp sgi/o2.cpp
        sony/news_r3k.cpp sony/news_r4k.cpp sony/news_68k.cpp sony/news_38xx.cpp sony/news_68k_iop.cpp
        nec/ews4800.cpp sun/ultra45.cpp hp/hp98x6.cpp hp/hp9k.cpp dec/jensen.cpp'''.split(),
    'Microcomputer': '''acorn/acrnsys.cpp acorn/acrnsys1.cpp mits/altair.cpp mits/mits680b.cpp
        nascom/nascom1.cpp commodore/kim1.cpp heathzenith/h8.cpp morrow/mpz80.cpp
        morrow/tricep.cpp nec/tk80bs.cpp tangerine/microtan.cpp'''.split(),
    'Minicomputer': ['dec/pdp11.cpp', 'fujitsu/secoinsa20.cpp'],
}
DRIVERS = {path: category for category, paths in FAMILIES.items() for path in paths}
SPECIALIZED = re.compile(r'logic analy[sz]er|teleprompter|\bgateway\b|\bHenson\b|Discmonitor|Discmate|'
    r'Etikettendrucker|processor board|Space Invasion|CNC Programming station|\bReuters APM\b', re.I)


def official_driver(url):
    try:
        parsed = urlsplit(url or '')
        if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.hostname not in ('github.com', 'www.github.com', 'raw.githubusercontent.com'):
            return None
        parts = parsed.path.strip('/').split('/')
        if parts[:2] != ['mamedev', 'mame'] or '/src/mame/' not in parsed.path:
            return None
        return parsed.path.split('/src/mame/', 1)[1]
    except ValueError:
        return None


def family_category(manufacturer, model, urls, legacy):
    if SPECIALIZED.search(model):
        return None
    urls = tuple(url for url in urls if isinstance(url, str))
    maker = maker_identity(manufacturer)
    public, core = model_names(model, manufacturer)
    names = {model, public, core, maker_aliases(manufacturer)[0] + ' ' + core}
    names |= {re.sub(r'(?<=[A-Za-z])(?=\d)', ' ', name) for name in list(names)}
    for rule_maker, pattern, category in (*EXTRA_RULES, *legacy):
        if maker == maker_identity(rule_maker) and any(re.search(pattern, name, re.I) for name in names):
            return {'category': category, 'rule': f'{rule_maker}: {pattern}', 'method': 'famiglia del modello'}
    # Explicit portable names can identify small brands without classifying
    # everything made by that manufacturer as a portable.
    if any(official_driver(url) for url in urls) and re.search(r'\b(?:Portable|Laptop|Notebook|Palmtop)\b', model, re.I):
        return {'category': 'Portable', 'rule': 'Denominazione esplicita di computer portatile con riferimento tecnico', 'method': 'denominazione del modello'}
    for url in sorted(urls):
        path = official_driver(url)
        category = ('Home computer' if path and path.startswith('msx/') else DRIVERS.get(path))
        if category:
            return {'category': category, 'rule': f'Famiglia hardware identificata: {path}',
                    'method': 'famiglia tecnica documentata', 'reference_url': url}
    return None


ROLES = (
    ('Portable', r'(?:personal\s+computer|computer|PC)\s+portatile|portatile|notebook|laptop|palmare|palmtop|handheld\s+PC'),
    ('Home computer', r'home\s+computer'), ('Workstation', r'workstation'),
    ('Mainframe', r'mainframe'), ('Supercomputer', r'supercomputer|supercalcolatore'),
    ('Minicomputer', r'minicomputer|minicalcolatore'), ('Server', r'server'),
    ('Personal computer', r'personal\s+computer|PC(?:\s+IBM)?\b'), ('Microcomputer', r'microcomputer'),
)


def description_category(manufacturer, model, description):
    text = description_text(description or '').strip()[:700]
    statement = re.match(r"^(?:L['’]|(?:Il|Lo|La)\s+)?(.{1,180}?)\s+(?:è|era|fu)\s+(?:un[oa]?|il\s+primo|la\s+prima)\s+(.+)", text, re.I)
    if not statement or model_key(manufacturer, statement[1]) != model_key(manufacturer, model):
        return None
    for category, pattern in ROLES:
        if re.match('(?:' + pattern + r')(?=\W|$)', statement[2], re.I):
            return {'category': category, 'rule': 'Tipo dichiarato nella frase introduttiva del modello',
                    'method': 'descrizione del sistema', 'excerpt': statement[0][:350]}
    return None
