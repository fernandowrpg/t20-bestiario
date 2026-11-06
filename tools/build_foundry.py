#!/usr/bin/env python3
"""Converte saida/threats.json (fichas extraídas do Bestiário de Arton) em documentos
Actor (type "npc") do sistema tormenta20 para Foundry VTT, no formato-fonte JSON do
@foundryvtt/foundryvtt-cli. Dados no formato do sistema 1.5.x (Foundry 13); o Foundry 14
(sistema 1.6.x) migra os documentos ao carregar.

Uso: python3 build_foundry.py threats.json magias_src_dir out_src_dir
"""
import json, re, sys, os, hashlib, html, glob, unicodedata, copy
import yaml

PACK = 'bestiario-de-arton'
MODULE = 'bestiario-de-arton-t20'
FONTE = 'Bestiário de Arton'
CORE = '13.351'
SYSVER = '1.5.015'

T20_PERICIAS = {  # key: (atributo, trainedOnly, armorPenalty, sizeMod)
    'acro': ('des', False, True, False), 'ades': ('car', True, False, False), 'atle': ('for', False, False, False),
    'atua': ('car', True, False, False), 'cava': ('des', False, False, False), 'conh': ('int', True, False, False),
    'cura': ('sab', False, False, False), 'dipl': ('car', False, False, False), 'enga': ('car', False, False, False),
    'fort': ('con', False, False, False), 'furt': ('des', False, True, True), 'guer': ('int', True, False, False),
    'inic': ('des', False, False, False), 'inti': ('car', False, False, False), 'intu': ('sab', False, False, False),
    'inve': ('int', False, False, False), 'joga': ('car', True, False, False), 'ladi': ('des', True, True, False),
    'luta': ('for', False, False, False), 'mist': ('int', True, False, False), 'nobr': ('int', True, False, False),
    'perc': ('sab', False, False, False), 'pilo': ('des', True, False, False), 'pont': ('des', False, False, False),
    'refl': ('des', False, False, False), 'reli': ('sab', True, False, False), 'sobr': ('sab', False, False, False),
    'vont': ('sab', False, False, False),
    'alfa': ('int', True, False, False), 'alqu': ('int', True, False, False), 'arme': ('int', True, False, False),
    'arte': ('int', True, False, False), 'cozi': ('int', True, False, False), 'enge': ('int', True, True, False),
}
SKILL_NAMES = {'acrobacia': 'acro', 'adestramento': 'ades', 'atletismo': 'atle', 'atuacao': 'atua', 'cavalgar': 'cava',
               'conhecimento': 'conh', 'cura': 'cura', 'diplomacia': 'dipl', 'enganacao': 'enga', 'fortitude': 'fort',
               'furtividade': 'furt', 'guerra': 'guer', 'iniciativa': 'inic', 'intimidacao': 'inti', 'intuicao': 'intu',
               'investigacao': 'inve', 'jogatina': 'joga', 'ladinagem': 'ladi', 'luta': 'luta', 'misticismo': 'mist',
               'nobreza': 'nobr', 'percepcao': 'perc', 'pilotagem': 'pilo', 'pontaria': 'pont', 'reflexos': 'refl',
               'religiao': 'reli', 'sobrevivencia': 'sobr', 'vontade': 'vont'}
OFICIOS = {'alfaiate': 'alfa', 'alquimista': 'alqu', 'armeiro': 'arme', 'ferreiro': 'arme', 'artesao': 'arte',
           'cozinheiro': 'cozi', 'engenhoqueiro': 'enge'}
LABELS = {}
SIZES = {'minusculo': 'min', 'minuscula': 'min', 'pequeno': 'peq', 'pequena': 'peq', 'medio': 'med', 'media': 'med',
         'grande': 'gra', 'enorme': 'eno', 'colossal': 'col'}
SIZE_MOD = {'min': 5, 'peq': 2, 'med': 0, 'gra': -2, 'eno': -5, 'col': -10}
TOKEN = {'min': 0.5, 'peq': 1, 'med': 1, 'gra': 2, 'eno': 3, 'col': 6}
TYPES = {'humanoide': 'hum', 'monstro': 'mon', 'espirito': 'esp', 'animal': 'ani', 'construto': 'con', 'morto-vivo': 'mor'}
ROLES = {'Solo': 'solo', 'Lacaio': 'lackey', 'Especial': 'special'}
DMG = {'acido': 'acido', 'corte': 'corte', 'eletricidade': 'eletricidade', 'essencia': 'essencia', 'fogo': 'fogo',
       'frio': 'frio', 'impacto': 'impacto', 'luz': 'luz', 'psiquico': 'psiquico', 'perfuracao': 'perfuracao',
       'trevas': 'trevas'}
ACTIONS = {'padrao': 'action', 'movimento': 'move', 'completa': 'full', 'reacao': 'reaction', 'livre': 'free'}
MOVES = {'voo': 'fly', 'natacao': 'swim', 'escalada': 'climb', 'escavacao': 'burrow', 'escalar': 'climb',
         'escavar': 'burrow', 'nadar': 'swim', 'voar': 'fly'}
SENSES = {'visao na penumbra': 'penumbra', 'visao no escuro': 'escuro', 'percepcao as cegas': 'cegas', 'faro': 'faro'}
IMG = {'hum': 'icons/svg/mystery-man.svg', 'mon': 'icons/svg/terror.svg', 'esp': 'icons/svg/aura.svg',
       'ani': 'icons/svg/terror.svg', 'con': 'icons/svg/terror.svg', 'mor': 'icons/svg/skull.svg'}


def norm(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn').lower().strip()


def fid(*parts):
    """_id determinístico de 16 caracteres alfanuméricos."""
    h = hashlib.sha256('|'.join(parts).encode()).digest()
    abc = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    return ''.join(abc[b % 62] for b in h[:16])


def stats(created=1790000000000):
    return {'systemId': 'tormenta20', 'systemVersion': SYSVER, 'coreVersion': CORE, 'createdTime': created,
            'modifiedTime': created, 'lastModifiedBy': None, 'compendiumSource': None, 'duplicateSource': None,
            'exportSource': None}


def split_top(s, seps=(', ', ' e ')):
    out, d, cur, i = [], 0, '', 0
    while i < len(s):
        c = s[i]
        if c == '(':
            d += 1
        elif c == ')':
            d -= 1
        if d == 0:
            hit = next((sp for sp in seps if s.startswith(sp, i)), None)
            if hit:
                out.append(cur); cur = ''; i += len(hit); continue
        cur += c; i += 1
    out.append(cur)
    return [x.strip(' .') for x in out if x.strip(' .')]


def p(text):
    return '<p>%s</p>' % html.escape(text, quote=False)


# ------------------------------------------------------------------ partes da ficha
def parse_defenses(text):
    """Converte imunidades/RD/vulnerabilidades a tipos de dano em tracos.resistencias.
    Devolve (resistencias, texto_restante)."""
    res = {k: {'value': 0, 'base': 0, 'bonus': [], 'imunidade': False, 'vulnerabilidade': False}
           for k in ['dano', 'perda'] + list(DMG)}
    keep = []
    # separa em cláusulas que começam por palavra-chave
    parts = re.split(r',\s*(?=(?:imunidade|redu[çc][ãa]o|vulnerabilidade|resist[êe]ncia|cura acelerada|evas[ãa]o|'
                     r'fortifica[çc][ãa]o|incorp[óo]reo|esquiva|[a-zà-ú]+ \+?\d))', text)
    for c in [x.strip() for x in parts if x.strip()]:
        n = norm(c); mapped = False
        m = re.fullmatch(r'reducao de dano (\d+)', n)
        if m:
            res['dano']['base'] = int(m.group(1)); mapped = True
        m = re.fullmatch(r'reducao de ([a-z ,]+?) (\d+)', n)
        if not mapped and m:
            kinds = [k for k in re.split(r',\s*|\s+e\s+', m.group(1)) if k]
            if kinds and all(k in DMG for k in kinds):
                for k in kinds:
                    res[k]['base'] = int(m.group(2))
                mapped = True
        m = re.fullmatch(r'(imunidade|vulnerabilidade) a (.+)', n)
        if not mapped and m:
            kinds = [re.sub(r'^dano de ', '', k).strip() for k in re.split(r',\s*|\s+e\s+', m.group(2))]
            flag = 'imunidade' if m.group(1) == 'imunidade' else 'vulnerabilidade'
            known = [k for k in kinds if k in DMG]
            for k in known:
                res[k][flag] = True
            mapped = len(known) == len(kinds)
            # "imunidade a dano de luz e trevas": dano de X marca o resto da lista também
            if not mapped and 'dano de' in m.group(2):
                tail = m.group(2).split('dano de', 1)[1]
                ks = [k.strip() for k in re.split(r',\s*|\s+e\s+', tail)]
                for k in ks:
                    if k in DMG:
                        res[k][flag] = True
        if not mapped:
            keep.append(c)
    # RD por dano também vale para os tipos (o sistema soma "dano" a todos os tipos)
    return res, ', '.join(keep)


def parse_senses(text):
    vals, custom = [], []
    for c in split_top(text, (', ',)):
        n = norm(c)
        if n in SENSES:
            vals.append(SENSES[n])
        else:
            custom.append(c)
    return vals, ', '.join(custom)


def parse_movement(text):
    mv = {k: {'base': 0, 'bonus': []} for k in ['walk', 'climb', 'burrow', 'swim', 'fly']}
    extra = []
    first = True
    for c in split_top(text, (', ',)):
        n = norm(c)
        m = re.fullmatch(r'(?:([a-z]+) )?([\d,]+)m(?: \(\d+ ?q\))?(.*)', n)
        if m and (m.group(1) is None or m.group(1) in MOVES):
            key = MOVES.get(m.group(1), 'walk')
            mv[key]['base'] = float(m.group(2).replace(',', '.'))
            if mv[key]['base'].is_integer():
                mv[key]['base'] = int(mv[key]['base'])
            if m.group(3).strip():
                extra.append(c)
        else:
            extra.append(c)
        first = False
    return mv, ', '.join(extra)


def parse_skill_line(texto):
    line = next((e for e in texto if re.match(r'^Perícias?\b', e)), '')
    out = {}
    body = re.sub(r'^Perícias?\s*', '', line)
    for item in split_top(body):
        m = re.match(r'^(.+?)\s*([+-]\s*\d+)', item)
        if not m:
            continue
        key = SKILL_NAMES.get(norm(m.group(1)))
        of = re.match(r'of[ií]cio\s*\((.+)\)', norm(m.group(1)))
        if of:
            key = OFICIOS.get(of.group(1).strip())
            if key:
                LABELS[key] = 'Ofício (%s)' % of.group(1).strip()
        if key:
            out[key] = int(m.group(2).replace(' ', ''))
        else:
            print('  perícia desconhecida:', item, file=sys.stderr)
    return out


def level_of(nd):
    if nd.upper().startswith('S'):
        return 20
    try:
        return int(nd)
    except ValueError:
        return 1   # 1/2, 1/4: o sistema usa Number(nd) || 1


def damage_parts(inside):
    """'2d8+8 mais 1d6 eletricidade, 19/x3, alcance 4,5m' -> (parts, criticoM, criticoX, extras)."""
    fields = [x.strip() for x in split_top(inside, (', ',))]
    dmg = fields[0] if fields else ''
    crit_m, crit_x, extras = 20, 2, []
    for f in fields[1:]:
        m = re.fullmatch(r'(\d+)(?:/x(\d))?', f)
        mx = re.fullmatch(r'x(\d)', f)
        if m:
            crit_m = int(m.group(1)); crit_x = int(m.group(2) or crit_x)
        elif mx:
            crit_x = int(mx.group(1))
        else:
            extras.append(f)
    parts = []
    for i, seg in enumerate(re.split(r'\s+mais\s+', dmg)):
        m = re.match(r'^(\d+d\d+(?:\s*[+-]\s*\d+)?|\d+)\s*(.*)$', seg.strip())
        if not m:
            extras.append(seg); continue
        formula = m.group(1).replace(' ', '')
        typ = DMG.get(norm(m.group(2)).replace('dano de ', ''), '')
        if i == 0:
            parts.append([formula, typ, ''])
            parts.append(['', '', ''])
        else:
            parts.append([formula, typ or ''])
        if m.group(2) and not typ:
            extras.append(seg.strip())
    if not parts:
        parts = [['0', '', ''], ['', '', '']]
    return parts, crit_m, crit_x, extras


def weapon_item(aid, idx, name, ranged, bonus, inside, skill_total, skill_key):
    parts, cm, cx, extras = damage_parts(inside)
    atk = bonus - skill_total
    iid = fid(aid, 'arma', str(idx), name)
    alcance = ''
    for e in extras:
        m = re.search(r'alcance (curto|médio|longo)', e)
        if m:
            alcance = {'curto': 'short', 'médio': 'medium', 'longo': 'long'}[m.group(1)]
    desc = '%s %+d (%s).' % (name, bonus, inside)
    return {
        '_id': iid, 'name': name, 'type': 'arma', 'img': 'icons/svg/sword.svg' if not ranged else 'icons/svg/target.svg',
        'effects': [], 'flags': {}, 'folder': None, 'sort': (idx + 1) * 100000, 'ownership': {'default': 0},
        'system': {
            'description': {'value': p(desc), 'chat': '', 'unidentified': ''},
            'source': FONTE, 'equipado': 1, 'carregado': True, 'peso': 0, 'espacos': 0, 'qtd': 1, 'preco': 0,
            'rolls': [
                {'name': 'Ataque', 'key': 'ataque0', 'type': 'ataque',
                 'parts': [['1d20', '', ''], [skill_key, 'des' if ranged else 'for', ''], [str(atk), '', '']], 'versatil': ''},
                {'name': 'Dano', 'key': 'dano1', 'type': 'dano', 'parts': parts, 'versatil': ''},
            ],
            'criticoM': cm, 'criticoX': cx, 'alcance': alcance, 'tipoUso': 'sim',
            'proficiencia': 'natural' if not ranged else 'simples',
            'proposito': 'disparo' if ranged else 'corpo-a-corpo', 'empunhadura': 'uma', 'size': 'normal',
            'ataques': 0,
        },
        '_stats': stats(), '_key': '!actors.items!%s.%s' % (aid, iid),
    }


def ability_item(aid, idx, name, desc):
    execucao, custo = 'passive', 0
    mn = re.match(r'^(.*?)\s*(\([^()]*\))$', name)
    if mn and norm(mn.group(2)[1:-1].split(',')[0]) in ACTIONS:
        name, desc = mn.group(1), mn.group(2) + ' ' + desc
    m = re.match(r'^\(([^)]*)\)\s*(.*)$', desc, re.S)
    if m:
        head = [norm(x) for x in m.group(1).split(',')]
        if head and head[0] in ACTIONS:
            execucao = ACTIONS[head[0]]
            for h in head[1:]:
                pm = re.match(r'(\d+) pm', h)
                if pm:
                    custo = int(pm.group(1))
    iid = fid(aid, 'poder', str(idx), name)
    body = ''.join(p(x) for x in desc.split('\n') if x.strip())
    return {
        '_id': iid, 'name': name, 'type': 'poder', 'img': 'icons/svg/book.svg', 'effects': [], 'flags': {},
        'folder': None, 'sort': (idx + 1) * 100000, 'ownership': {'default': 0},
        'system': {
            'description': {'value': body, 'unidentified': ''}, 'source': FONTE,
            'ativacao': {'execucao': execucao, 'custo': custo, 'qtd': '', 'condicao': '', 'special': ''},
            'rolls': [], 'tipo': 'ability', 'subtipo': '',
        },
        '_stats': stats(), '_key': '!actors.items!%s.%s' % (aid, iid),
    }


def load_spells(src_dir):
    idx = {}
    for f in glob.glob(os.path.join(src_dir, '**', '*.yml'), recursive=True):
        d = yaml.safe_load(open(f))
        if d and d.get('type') == 'magia':
            idx[norm(d['name'])] = d
    return idx


SPELL_ALIASES = {}


def spell_item(aid, idx, sp, spells, hdr):
    base = re.sub(r'\s*\(\d+ PM\)$', '', sp['namespell']).strip()
    src = spells.get(norm(SPELL_ALIASES.get(base, base)))
    uso = '%s %s' % (base, sp['spelldescription'].strip())
    if not src:
        it = ability_item(aid, 500 + idx, base, '%s\n%s' % (sp['spelldescription'], hdr or ''))
        it['img'] = 'icons/svg/daze.svg'
        return it, False
    it = copy.deepcopy(src)
    iid = fid(aid, 'magia', base)
    it.pop('folder', None)
    it.update({'_id': iid, 'folder': None, 'sort': (600 + idx) * 100000, '_key': '!actors.items!%s.%s' % (aid, iid)})
    it['system']['description']['value'] = (
        '<section class="secret"><p><strong>Uso pela criatura:</strong> %s</p></section>' % html.escape(uso, quote=False)
        + it['system']['description']['value'])
    it['_stats'] = dict(stats(), compendiumSource='Compendium.tormenta20.magias.%s' % src['_id'])
    for e in it.get('effects', []):
        e['_key'] = '!actors.items.effects!%s.%s.%s' % (aid, iid, e['_id'])
        e['origin'] = None
    return it, True


# ------------------------------------------------------------------ ator
def actor(t, spells, folders, stat):
    aid = fid('BdA', t['nome'], str(t['pagina']))
    mods = t['mods']
    nd = t['nd']
    nivel = level_of(nd)
    meio = nivel // 2
    treino = 6 if nivel > 14 else 4 if nivel > 6 else 2

    tipo_txt = t['tipo']
    words = tipo_txt.split()
    tsize = SIZES.get(norm(words[-1]), 'med') if words else 'med'
    ctype = TYPES.get(norm(words[0]), 'mon') if words else 'mon'
    sub = re.search(r'\(([^)]*)\)', tipo_txt)
    raca = [sub.group(1)] if sub else []
    raca += [x.lower() for x in t['icons'] if x in ('Bando', 'Enxame')]
    role = next((ROLES[x] for x in t['icons'] if x in ROLES), 'solo')

    # perícias
    LABELS.clear()
    listed = parse_skill_line(t['texto'])
    sk = t['skills']
    totals = {'inic': sk.get('iniciativa', 0), 'perc': sk.get('percepcao', 0), 'fort': sk['fortitude'],
              'refl': sk['reflexos'], 'vont': sk['vontade']}
    melee = [a for a in t['attacks'] if a['ataquealcance'] != 'Distância']
    ranged = [a for a in t['attacks'] if a['ataquealcance'] == 'Distância']
    book_bonus = lambda a: int(re.search(r'\+(\d+) \(', a['ataquedescricao']).group(1))
    pericias = {}
    for key, (atr, st, pda, size) in T20_PERICIAS.items():
        d = {'value': 0, 'atributo': atr, 'outros': 0, 'treinado': False, 'st': st, 'pda': pda, 'size': size,
             'condi': 0, 'bonus': [], 'custom': False, 'label': '', 'nome': ''}
        total, trained = None, False
        if key in listed:
            total, trained = listed[key], True
        elif key in totals:
            total = totals[key]
        elif key == 'luta' and melee:
            total = book_bonus(melee[0])
        elif key == 'pont' and ranged:
            total = book_bonus(ranged[0])
        if total is not None:
            szm = SIZE_MOD[tsize] if size else 0
            d['treinado'] = trained
            d['outros'] = total - meio - mods[atr] - (treino if trained else 0) - szm
            d['value'] = total
            d['label'] = LABELS.get(key, '') if key in OFICIOS.values() else ''
        pericias[key] = d
    luta_total = pericias['luta']['value'] if (melee or 'luta' in listed) else meio + mods['for']
    pont_total = pericias['pont']['value'] if (ranged or 'pont' in listed) else meio + mods['des']

    # itens
    items = []
    for i, a in enumerate(t['attacks']):
        r = a['ataquealcance'] == 'Distância'
        inside = re.match(r'Livro: .*? \+\d+ \((.*)\)$', a['ataquedescricao']).group(1)
        items.append(weapon_item(aid, i, a['nomeataque'], r, book_bonus(a), inside,
                                 pont_total if r else luta_total, 'pont' if r else 'luta'))
    spell_hdr = None
    for i, ab in enumerate(t['abilities']):
        if re.match(r'^Magias?\b', ab['nameability']) and t['spells']:
            spell_hdr = '%s %s' % (ab['nameability'], ab['abilitydescription'].split('\n')[0])
            continue
        items.append(ability_item(aid, 100 + i, ab['nameability'], ab['abilitydescription']))
    for i, sp in enumerate(t['spells']):
        it, ok = spell_item(aid, i, sp, spells, spell_hdr)
        stat['spells_ok' if ok else 'spells_missing'].append(sp['namespell'] if ok else '%s (%s)' % (sp['namespell'], t['nome']))
        items.append(it)
    if spell_hdr and items:
        # cabeçalho "Magias (CD x) ..." como habilidade de referência
        items.append(ability_item(aid, 99, 'Magias', spell_hdr.split(' ', 1)[1] if ' ' in spell_hdr else ''))

    # CD de magias/habilidades
    cd = t['spellcd'] or 0
    if not cd:
        cds = [int(x) for x in re.findall(r'CD (\d+)', ' '.join(t['texto']))]
        cd = max(set(cds), key=cds.count) if cds else 10

    res, res_txt = parse_defenses(t['defesas_especiais'])
    sens, sens_custom = parse_senses(t['sentidos'])
    mv, mv_txt = parse_movement(t['deslocamento'])
    ataques_cac = next((e[len('Corpo a Corpo '):] for e in t['texto'] if e.startswith('Corpo a Corpo')), '')
    ataques_ad = next((e.split(' ', 2)[2] for e in t['texto'] if e.startswith(('À Distância', 'A Distância'))), '')
    tes = re.search(r'Tesouro\s+(.*?)\.?$', t['tesouro'] or '')
    equip = re.sub(r'^Equipamento\s*', '', t['equipamento']).split(' Tesouro')[0].strip()

    fonte = '%s, p. %d' % (FONTE, t['pagina'])
    bio = '<p><em>%s — ND %s · %s%s</em></p>' % (html.escape(t['nome']), nd, html.escape(tipo_txt),
                                                  (' · ' + ' · '.join(t['icons'])) if t['icons'] else '')
    bio += ''.join(p(e) for e in t['texto'])
    bio += '<p><strong>Fonte:</strong> %s</p>' % html.escape(fonte)

    w = TOKEN[tsize]
    folder = folders[nd]
    return {
        '_id': aid, 'name': t['nome'], 'type': 'npc', 'img': IMG[ctype], 'items': items, 'effects': [],
        'folder': folder, 'sort': 0,
        'flags': {MODULE: {'fonte': fonte}},
        'system': {
            'atributos': {k: {'value': 0, 'bonus': 0, 'base': v, 'racial': 0} for k, v in mods.items()},
            'attributes': {
                'cd': cd,
                'pv': {'value': t['pv'], 'min': -(t['pv'] // 2), 'max': t['pv'], 'temp': 0},
                'pm': {'value': t['pm'], 'min': 0, 'max': t['pm'], 'temp': 0},
                'movement': dict(mv, unit='m', hover='pairar' in norm(t['deslocamento']), tags=[]),
                'defesa': {'base': 10, 'value': t['defesa'], 'outros': t['defesa'] - 10 - mods['des'], 'atributo': 'des',
                           'pda': 0, 'bonus': [], 'condi': 0},
                'sentidos': {'value': sens, 'custom': sens_custom},
                'conjuracao': 'int', 'nivel': {'value': nivel, 'xp': {'value': 0}}, 'nd': nd, 'treino': 0,
            },
            'detalhes': {
                'biography': {'value': bio, 'public': ''}, 'raca': ', '.join(raca), 'tipo': ctype, 'divindade': '',
                'origem': '', 'equipamento': equip, 'resistencias': res_txt, 'movimento': mv_txt,
                'tesouro': tes.group(1) if tes else '', 'role': role, 'ataquescac': '', 'ataquesad': '',
            },
            'tracos': {'tamanho': tsize, 'resistencias': res, 'ic': {'value': [], 'custom': ''}},
            'pericias': pericias,
        },
        'ownership': {'default': 0},
        'prototypeToken': {
            'name': t['nome'], 'displayName': 20, 'actorLink': False, 'disposition': -1, 'displayBars': 20,
            'width': w, 'height': w, 'bar1': {'attribute': 'attributes.pv'}, 'bar2': {'attribute': 'attributes.pm'},
            'texture': {'src': IMG[ctype], 'scaleX': 1, 'scaleY': 1, 'fit': 'contain'},
            'sight': {'enabled': True, 'range': 0, 'visionMode': 'basic'},
            'appendNumber': True, 'flags': {},
        },
        '_stats': stats(), '_key': '!actors!%s' % aid,
    }, (ataques_cac, ataques_ad)


ND_ORDER = lambda nd: (21 if nd.upper().startswith('S') else (0.25 if nd == '1/4' else 0.5 if nd == '1/2' else int(nd)))


def main(threats_path, magias_dir, out_dir):
    T = json.load(open(threats_path))
    spells = load_spells(magias_dir)
    os.makedirs(out_dir, exist_ok=True)
    for f in glob.glob(os.path.join(out_dir, '*.json')):
        os.remove(f)
    folders = {}
    for nd in sorted({t['nd'] for t in T}, key=ND_ORDER):
        fidv = fid('folder', nd)
        folders[nd] = fidv
        label = 'ND %s' % nd
        doc = {'_id': fidv, 'name': label, 'type': 'Actor', 'folder': None, 'sorting': 'a',
               'sort': int(ND_ORDER(nd) * 1000), 'color': None, 'flags': {}, '_stats': stats(),
               '_key': '!folders!%s' % fidv}
        json.dump(doc, open(os.path.join(out_dir, 'folder_%s.json' % re.sub(r'\W', '_', nd)), 'w'), ensure_ascii=False, indent=1)
    stat = {'spells_ok': [], 'spells_missing': []}
    names = set()
    for t in T:
        a, _ = actor(t, spells, folders, stat)
        assert a['_id'] not in names, a['name']
        names.add(a['_id'])
        slug = re.sub(r'[^a-z0-9]+', '-', norm(a['name'])).strip('-')
        json.dump(a, open(os.path.join(out_dir, '%s_%s.json' % (slug, a['_id'])), 'w'), ensure_ascii=False, indent=1)
    print('%d atores, %d magias ligadas ao compêndio, %d magias sem correspondência'
          % (len(T), len(stat['spells_ok']), len(stat['spells_missing'])), file=sys.stderr)
    for s in stat['spells_missing']:
        print('  sem correspondência:', s, file=sys.stderr)


if __name__ == '__main__':
    main(*sys.argv[1:4])
