#!/usr/bin/env python3
"""Extrai fichas de ameaças de PDFs de Tormenta20 (Jambo) e gera dados para a ficha
"Tormenta20 - Jogo do Ano" do Roll20 (modo ameaça, cstype=1), no formato do
importador do Grimório do Tormenta20 + campos menace_*.

Uso:  python3 t20ameacas.py config.json   (gera out_dir/data.js, threats.json, review.txt, json/)
page_offset: soma ao número da página do PDF (1-based) para obter a página impressa.
"""
import json, re, sys, os, math, unicodedata
import pdfplumber

# ---------------------------------------------------------------- constantes
TYPES = re.compile(r'^(Humanoide|Monstro|Esp[ií]rito|Animal|Construto|Morto-vivo|Lefeu|Fera|Planta|Elemental|Ser)\b', re.I)
ATTR_OF = {'acrobacia':'des','adestramento':'car','atletismo':'for','atuacao':'car','cavalgar':'des','conhecimento':'int','cura':'sab',
 'diplomacia':'car','enganacao':'car','fortitude':'con','furtividade':'des','guerra':'int','iniciativa':'des','intimidacao':'car',
 'intuicao':'sab','investigacao':'int','jogatina':'car','ladinagem':'des','luta':'for','misticismo':'int','nobreza':'int','oficio':'int',
 'oficio2':'int','percepcao':'sab','pilotagem':'des','pontaria':'des','reflexos':'des','religiao':'sab','sobrevivencia':'sab','vontade':'sab'}
SKF = {'for':'@{for_mod} + @{condicaoperfisico} + @{condicaocego}','des':'@{des_mod} + @{condicaoperfisico} + @{condicaocego}',
 'con':'@{con_mod} + @{condicaoperfisico}','int':'@{int_mod} + @{condicaopermental}','sab':'@{sab_mod} + @{condicaopermental}',
 'car':'@{car_mod} + @{condicaopermental}'}
MELEE = '@{lutatotal}+@{condicaomodataquecc}+@{condicaomodataque}'
AIM = '@{pontariatotal}+@{condicaomodataquedis}+@{condicaomodataque}'
DMGTYPES = ['corte','perfuração','impacto','fogo','frio','ácido','eletricidade','luz','trevas','essência','psíquico','gelo','sônico']
FIXED = ('Iniciativa','Defesa','Pontos de Vida','Deslocamento','Pontos de Mana','Corpo a Corpo','À Distância','A Distância','For ',
         'Perícia','Equipamento','Tesouro')
CONT = ('Fort', 'Ref', 'Von', 'Percepção', 'Des', 'Con', 'Int', 'Sab', 'Car')   # negrito que continua a linha anterior
TAM = {'minúsculo':5,'minúscula':5,'pequeno':2,'pequena':2,'médio':0,'média':0,'grande':-2,'enorme':-5,'colossal':-10}
# assinatura vetorial (nº de pontos das curvas) dos ícones de papel de combate
ICON = [('7-51','Solo'),('11-22','Especial'),('18-18','Lacaio'),('17-17-19','Enxame')]
def icon_name(sig):
    if sig == '19': return 'Bando'
    for k, v in ICON:
        if k in sig: return v
    return '?' + sig
CONDS = ('abalado agarrado alquebrado apavorado atordoado caido cego confuso debilitado desprevenido doente emchama enfeiticado enjoado '
         'enreado envenenado esmorecido exausto fascinado fatigado fraco frustrado imovel inconsciente indefeso lento ofuscado paralizado '
         'pasmo petrificacao sangrando surdo surpreendido vulneravel').split()

def degarble(x):
    """Negrito com kerning ruim: cada espaço sai 1 letra à direita ("Rompero sG rilhões(Movimento)")."""
    c = list(x)
    for i in range(1, len(c)):
        if c[i] == ' ' and c[i - 1] != ' ': c[i - 1], c[i] = c[i], c[i - 1]
    return re.sub(r'(\S)\(', r'\1 (', ''.join(c))

def norm(s): return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn').lower()
def num(s): return int(s.replace('.', '').replace('–', '-').replace('−', '-'))
def clean(s):
    s = s.replace('–', '-').replace('−', '-').replace(' ,', ',').replace(' .', '.').replace('( ', '(').replace(' )', ')').replace(' ;', ';')
    s = re.sub(r'\s+', ' ', s).strip()
    s = re.sub(r'(?<![\w-])([B-DF-NP-Z]) ([a-zà-ú]{2,})', r'\1\2', s)   # inicial de versalete descolada ("D efesa")
    return re.sub(r'\s+e$', '', s)   # glifo de ícone que vira " e" no fim do parágrafo

# ---------------------------------------------------------------- 1. fluxo de linhas por coluna, só fontes de ficha
def icon_sigs(pg, x1, top, bot):
    objs = [o for o in pg.curves + pg.rects + pg.lines if x1 - 1 <= o['x0'] < x1 + 60 and o['top'] > top - 6 and o['bottom'] < bot + 6]
    objs.sort(key=lambda o: o['x0']); groups = []
    for o in objs:
        if groups and o['x0'] <= groups[-1]['x1'] + 1.0:
            groups[-1]['o'].append(o); groups[-1]['x1'] = max(groups[-1]['x1'], o['x1'])
        else: groups.append({'x1': o['x1'], 'o': [o]})
    return ['-'.join(str(n) for n in sorted(len(o.get('pts') or []) for o in g['o'])) for g in groups]

def stream(path):
    lines = []
    with pdfplumber.open(path) as p:
        for pn, pg in enumerate(p.pages):
            mid = pg.width / 2; keep = []
            for c in pg.chars:   # versalete (Deuses de Arton): minúsculas em corpo menor e caixa trocada
                if 'SourceSans' in c['fontname'] and 'SC' in c['fontname'].split('-')[-1] and c['size'] >= 8:
                    c['text'] = c['text'].upper(); c['x1'] += 1.2
                elif 'SourceSans' in c['fontname'] and 'SC' in c['fontname'].split('-')[-1] and c['size'] < 8:
                    mid_y = (c['top'] + c['bottom']) / 2; d = (mid_y - 4.5) - c['top']
                    c['top'] += d; c['doctop'] += d; c['bottom'] = mid_y + 4.5
                    c['text'] = c['text'].lower(); c['size'] = 9.0
            for w in pg.extract_words(extra_attrs=['fontname', 'size'], x_tolerance=1.5):
                f = w['fontname']
                if 'SourceSans' in f and 8 < w['size'] < 10: w['kind'] = 'b' if ('Bold' in f or 'Black' in f) else ('i' if '-It' in f else 's')
                elif 'Tormenta20' in f and 10.5 <= w['size'] < 22.5 and w['top'] < pg.height - 55: w['kind'] = 'T'   # (rodapé = nº de página)
                else: continue
                keep.append(w)
            # agrupa por altura, quebra cada linha em segmentos onde há vão > 10pt (calha entre colunas);
            # segmento contínuo que cruza o meio da página (caixas largas) continua inteiro.
            rows = []
            for w in sorted(keep, key=lambda w: w['top']):
                if rows and w['top'] - rows[-1][-1]['top'] <= 1.5: rows[-1].append(w)
                else: rows.append([w])
            segs = []
            for r in rows:
                r.sort(key=lambda w: w['x0']); cur = [r[0]]
                for w in r[1:]:
                    gap = w['x0'] - cur[-1]['x1']
                    if gap > 10 or (gap > 4.5 and cur[-1]['x1'] <= mid + 8 and w['x0'] >= mid - 8): segs.append(cur); cur = [w]
                    else: cur.append(w)
                segs.append(cur)
            # marcador "•" isolado (baseline diferente): cola no segmento à direita mais próximo
            for bseg in [c for c in segs if len(c) == 1 and c[0]['text'] == '•']:
                alvo = [c for c in segs if c is not bseg and 0 < c[0]['x0'] - bseg[0]['x1'] < 20 and abs(c[0]['top'] - bseg[0]['top']) < 5]
                if alvo:
                    a = min(alvo, key=lambda c: abs(c[0]['top'] - bseg[0]['top'])); a.insert(0, bseg[0]); segs.remove(bseg)
            for col in (0, 1):
                for cur in sorted([c for c in segs if (c[0]['x0'] < mid - 5) == (col == 0)], key=lambda c: (min(x['top'] for x in c), c[0]['x0'])):
                    i = 0
                    while i < len(cur) and cur[i]['kind'] == 'b': i += 1
                    L = {'p': pn, 't': ' '.join(x['text'] for x in cur), 'b': ' '.join(x['text'] for x in cur[:i]),
                         'T': all(x['kind'] == 'T' for x in cur), 'top': min(x['top'] for x in cur if x['text'] != '•') if len(cur) > 1 else cur[0]['top'], 'x0': cur[0]['x0'],
                         'it': all(x['kind'] == 'i' for x in cur)}
                    if L['it']:
                        L['icons'] = [icon_name(s) for s in icon_sigs(pg, max(x['x1'] for x in cur), L['top'], max(x['bottom'] for x in cur))]
                    lines.append(L)
    return lines

# ---------------------------------------------------------------- 2. blocos
def join(a, b):
    if a.endswith('-') and len(a) > 1 and a[-2].isalpha(): return a[:-1] + b
    return a + ' ' + b

def blocks(L, src):
    out = []
    for i, l in enumerate(L):
        if l['b'] != 'Iniciativa' or not l['t'].startswith('Iniciativa'): continue
        j = i - 1; tipo = None; icons = []
        if j >= 0 and (TYPES.match(L[j]['t']) or L[j].get('it')): tipo = L[j]['t']; icons = L[j].get('icons', []); j -= 1
        hdr = []
        lim = L[j + 1]['top'] if j + 1 < len(L) else l['top']
        hp = l['p']
        while j >= 0 and L[j]['T'] and len(hdr) < 4:
            if hdr and not (L[j]['p'] == hp and 0 <= lim - L[j]['top'] < 24): break
            if not hdr and L[j]['p'] not in (l['p'], l['p'] - 1): break   # cabeçalho pode estar no fim da coluna/página anterior
            hdr.insert(0, L[j]['t']); lim = L[j]['top']; hp = L[j]['p']; j -= 1
            if re.match(r'^\S.*\sN[Dd]\s*\S+$', hdr[0]): break   # linha "Nome ND x" completa: não subir mais
        nd = None; name = []
        for h in hdr:
            m = re.match(r'^(.*?)\s*ND\s*([0-9/]+|[Ss]\s*\+?)$', h)
            if m:
                nd = m.group(2).upper().replace(' ', '')
                if m.group(1): name.append(m.group(1))
            else: name.append(h)
        if name and name[-1].endswith('ND'): name[-1] = name[-1][:-2].strip()
        name = [n for k2, n in enumerate(name) if n and n not in name[:k2]]
        name = [n for n in name if not any(o != n and o.startswith(n) for o in name)]   # título de seção repetindo o nome
        ref = L[j + 1]['top'] if j + 1 < i else l['top']
        near = [x for x in L if x['p'] == l['p'] and x['T'] and -45 < x['top'] - ref < 25]
        if nd is None:   # selo de ND caiu na outra coluna: procura na mesma página, mesma altura
            c = [x for x in near if re.match(r'^(ND\s*)?([0-9/]+|[Ss]\s*\+?)$', x['t'])]
            if c: nd = re.match(r'^(?:ND\s*)?(.+)$', min(c, key=lambda x: abs(x['top'] - ref))['t']).group(1).upper().replace(' ', '')
        if not name:     # nome caiu na outra coluna
            c = [x for x in near if not re.search(r'\bND\b|^[0-9/S+ ]+$', x['t']) and x['top'] <= ref]
            if c: name = [max(c, key=lambda x: x['top'])['t']]
        ents = []; k = i; intes = False; bolds = []
        while k < len(L):
            x = L[k]
            if x['T'] and re.match(r'^(ND\b.*|[0-9/Ss+ ]+)$', x['t']): k += 1; continue   # selo de ND de outro bloco
            if k > i and (x['T'] or x['b'] == 'Iniciativa'): break
            if intes and x['b'] and not re.match(r'^(Parceir[oa]|Aliado)', x['b']): break   # seção de parceiro continua
            t = x['t']
            if x['b']: bolds.append(x['b'])
            starts = x['b'] and x['b'].split()[0].rstrip(',') not in CONT
            if ents and t.startswith('(') and len(ents[-1]) < 45 and not re.search(r'[.)]$', ents[-1]): ents[-1] = ents[-1] + ' ' + t
            elif starts or t.startswith('•') or not ents: ents.append(t)
            else: ents[-1] = join(ents[-1], t)
            if x['b'].startswith('Tesouro') or (re.search(r'\bTesouro\b', t) and ents[-1].startswith('Equipamento')): intes = True
            k += 1
            if intes and ents[-1].rstrip().endswith('.') and not (k < len(L) and re.match(r'^(Parceir[oa]|Aliado)', L[k]['b'])): break
        out.append({'src': src['id'], 'page': l['p'] + 1 + src.get('page_offset', 0), 'nome': ' '.join(name).replace('- ', '-').strip(),
                    'nd': nd or '?', 'tipo': tipo, 'icons': icons, 'entries': ents, 'bolds': bolds})
    return out

# ---------------------------------------------------------------- 3. ficha estruturada
def split_top(s):
    parts = []; d = 0; cur = ''; i = 0
    while i < len(s):
        c = s[i]
        if c == '(': d += 1
        if c == ')': d -= 1
        if d == 0:
            for sep in (', ', ' e ', ' ou '):
                if s.startswith(sep, i): parts.append(cur); cur = ''; i += len(sep); break
            else: cur += c; i += 1
            continue
        cur += c; i += 1
    parts.append(cur)
    out = []
    for p in [p.strip(' .') for p in parts if p.strip(' .')]:
        if out and not re.search(r'[+-]\s*\d+\s*(\(|$)', out[-1]) and re.search(r'\+\s*\d+\s*\(', p): out[-1] += ' e ' + p
        else: out.append(p)
    return out

def parse_attacks(text, ranged, mods, half, skills):
    out = []
    for p in split_top(text):
        m = re.match(r'^(?:\[Bando\]\s*)?(?P<nome>.+?)\s*\+\s*(?P<b>\d+)\s*\((?P<in>.*)\)?$', p)
        if not m: continue
        nome = m.group('nome').strip(); nome = nome[0].upper() + nome[1:]
        bonus = int(m.group('b')); inside = m.group('in').rstrip(')')
        parts = [x.strip() for x in inside.split(',')]
        margem, mult, desc = '20', '2', []
        for x in parts[1:]:
            mc = re.fullmatch(r'(\d+)(?:/x(\d))?', x); mx = re.fullmatch(r'x(\d)', x)
            if mc: margem = mc.group(1); mult = mc.group(2) or mult
            elif mx: mult = mx.group(1)
            else: desc.append(x)
        dm = re.match(r'^(\d+d\d+)\s*([+-]\s*\d+)?\s*(.*)$', parts[0]); dice, flat, tipo = '0', 0, ''
        if dm:
            dice = dm.group(1); flat = int(dm.group(2).replace(' ', '')) if dm.group(2) else 0
            if dm.group(3).strip() in DMGTYPES: tipo = dm.group(3).strip()
        else:
            fm = re.match(r'^(\d+)\b', parts[0]); flat = int(fm.group(1)) if fm else 0
        sk = 'pontaria' if ranged else 'luta'
        skt = skills.get(sk, half + mods[ATTR_OF[sk]])
        out.append({'nomeataque': nome, 'bonusataque': str(bonus - skt), 'danoataque': dice, 'danoextraataque': str(flat - mods['for']),
                    'dadoextraataque': '0', 'margemcriticoataque': margem, 'multiplicadorcriticoataque': mult,
                    'ataquedescricao': 'Livro: %s +%d (%s)' % (nome, bonus, inside), 'ataquepericia': AIM if ranged else MELEE,
                    'ataquetipodedano': tipo, 'ataquealcance': 'Distância' if ranged else 'Corpo a corpo',
                    'modatributodano': '@{for_mod}', 'tipocritico': ''})
    return out

SKN = {norm(k): k for k in ATTR_OF}

def level(nd):
    """(charnivel para a ficha, metade do nível usada pela ficha)"""
    if nd.startswith('S'): return '20', 10
    if nd == '1/4': return '.3', 0
    if '/' in nd: return '.5', 0
    try: n = int(nd)
    except ValueError: n = 1
    return str(n), n // 2

def build(b, name_fix):
    k3 = '%s:%s:%s' % (b['src'], b['page'], b['nome'])
    nome = name_fix.get(k3, name_fix.get('%s:%s' % (b['src'], b['page']), name_fix.get(b['nome'], b['nome'])))
    if k3 in b.get('nd_fix', {}): b['nd'] = b['nd_fix'][k3]
    if k3 in b.get('tipo_fix', {}): b['tipo'] = b['tipo_fix'][k3]; b['icons'] = b['icons'] or ['Solo']
    nome = re.sub(r'\s*\bN[Dd]\s*\S*$', '', nome or '').strip()
    if nome: nome = nome[0].upper() + nome[1:]
    E = [clean(e) for e in b['entries'] if not re.fullmatch(r'((.)\2)+', e.replace(' ', ''))]   # títulos com letras duplicadas
    bolds = [clean(x) for x in b['bolds']]
    for old, new in b.get('text_fix', []):
        E = [e.replace(old, new) for e in E]; bolds = [x.replace(old, new) for x in bolds] + ([new] if len(new) < 60 else [])
    for x in [x for x in bolds if re.search(r'[a-zà-ú][A-ZÀ-Ú]', x) and len(x) > 4]:
        g = degarble(x); E = [g + e[len(x):] if e.startswith(x) else e for e in E]; bolds.append(g)
    bolds = sorted(set(bolds), key=len, reverse=True)
    get = lambda pre: next((e for e in E if e.startswith(pre)), '')
    charnivel, half = level(b['nd'])
    mods = {k.lower(): (0 if v in ('—', '-') else int(v)) for k, v in re.findall(r'(For|Des|Con|Int|Sab|Car)\s*([+-]?\d+|—|-(?!\d))', get('For '))}
    for k in ['for', 'des', 'con', 'int', 'sab', 'car']: mods.setdefault(k, 0)
    skills = {}; sentidos = ''
    mi = re.match(r'Iniciativa \+?(-?\d+), Percepção \+?(-?\d+)(.*)', get('Iniciativa'))
    if mi: skills['iniciativa'] = int(mi.group(1)); skills['percepcao'] = int(mi.group(2)); sentidos = mi.group(3).strip(' ,')
    md = re.match(r'Defesa (\d+)(?:\s*\([^)]*\))?, Fort \+?(-?\d+), Ref \+?(-?\d+), Von \+?(-?\d+)(.*)', get('Defesa'))
    if not md: raise ValueError('linha de Defesa ilegível')
    defesa = int(md.group(1)); skills.update(fortitude=int(md.group(2)), reflexos=int(md.group(3)), vontade=int(md.group(4)))
    pvm = re.search(r'[\d.]+', get('Pontos de Vida')); pv = num(pvm.group()) if pvm else 0
    pmm = re.search(r'[\d.]+', get('Pontos de Mana')); pm = num(pmm.group()) if pmm else 0
    desl = get('Deslocamento')[len('Deslocamento '):]
    oficionome = ''
    for item in split_top(re.sub(r'^Perícias?\s*', '', get('Perícia')).replace(' e ', ', ')):
        m = re.match(r'^(.+?)\s*\+\s*(-?\d+)\s*(\(.*\))?$', item.strip(' .'))
        if not m: continue
        nm = m.group(1).strip(); mo = re.match(r'Of[ií]cio\s*\((.*)\)', nm)
        key = 'oficio' if mo else SKN.get(norm(nm))
        if mo: oficionome = mo.group(1)
        if key: skills[key] = int(m.group(2))
    attacks, abilities, spells = [], [], []; magias_hdr = None
    for idx, e in enumerate(E):
        if e.startswith('Corpo a Corpo'): attacks += parse_attacks(e[len('Corpo a Corpo '):], False, mods, half, skills); continue
        if e.startswith(('À Distância', 'A Distância')): attacks += parse_attacks(e.split(' ', 2)[2], True, mods, half, skills); continue
        if e.startswith(FIXED): continue
        if e.startswith('•'):
            m = re.match(r'•\s*(.+?)\s*\(([^)]*)\)\s*(.*)', e)
            if magias_hdr is not None and m:
                inn = m.group(2); pmc = re.search(r'(\d+) PM', inn)
                spells.append({'namespell': re.sub(r'\b(\w) (\w)', r'\1\2', m.group(1)) if len(m.group(1).split()[0]) == 1 else m.group(1),
                               'spelltipo': '', 'spellcd': '0', 'spellexecucao': inn.split(',')[0].strip(), 'spellalcance': '',
                               'spellduracao': 'sustentada' if 'sustentada' in inn else '', 'spellalvoarea': '', 'spellresistencia': '',
                               'spelldescription': '(%s) %s' % (inn, m.group(3))})
                if pmc: spells[-1]['namespell'] += ' (%s PM)' % pmc.group(1)
            elif abilities: abilities[-1]['abilitydescription'] += '\n' + e
            continue
        name = next((x for x in bolds if e.startswith(x)), None) or e.split(' ')[0]
        if name.startswith('Aura Aterradora'): name = 'Aura Aterradora'
        desc = e[len(name):].strip(); name = name.rstrip(':')
        if re.match(r'^Magias?\b', name) and idx + 1 < len(E) and E[idx + 1].startswith('•'): magias_hdr = desc
        abilities.append({'nameability': name, 'abilitydescription': desc})
    cdm = re.search(r'CD (\d+)', magias_hdr or '')
    return {'nome': nome, 'nd': b['nd'], 'tipo': b['tipo'] or '', 'src': b['src'], 'pagina': b['page'], 'icons': b['icons'],
            'charnivel': charnivel, 'half': half, 'mods': mods, 'skills': skills, 'defesa': defesa, 'pv': pv, 'pm': pm,
            'deslocamento': desl, 'sentidos': sentidos, 'defesas_especiais': md.group(5).strip(' ,'),
            'equipamento': get('Equipamento'), 'tesouro': get('Tesouro'), 'attacks': attacks, 'abilities': abilities,
            'spells': spells, 'spellcd': int(cdm.group(1)) if cdm else None, 'oficionome': oficionome, 'texto': E}

# ---------------------------------------------------------------- 4. ficha do Roll20 (Grimório + modo ameaça)
def sheet(t, label):
    h = t['half']; m = t['mods']; sk = t['skills']
    tam = TAM.get((t['tipo'].split() or ['médio'])[-1].lower(), 0)
    roles = [r for r in t['icons'] if r in ('Solo', 'Lacaio', 'Especial')] or ['Solo']
    papel = ', '.join([roles[0]] + [x for x in ('Bando', 'Enxame') if x in t['icons']])
    fonte = '%s, p. %d' % (label, t['pagina'])
    d = {'isJDA': True, 'playername': '', 'trace': t['tipo'], 'torigin': fonte, 'tlevel': 'Ameaça ND %s' % t['nd'], 'charnivel': t['charnivel']}
    for k in m: d[k] = str(m[k])
    d.update({'vidatotal': str(t['pv']), 'vida': str(t['pv']), 'vidatemp': '0', 'manatotal': str(t['pm']), 'mana': str(t['pm']), 'manatemp': '0',
              'defesaatributo': '1', 'defesaoutros': str(t['defesa'] - 10 - m['des']), 'ts': '0', 'to': '0',
              'proficiencias': '\n'.join(x for x in ['Sentidos: ' + t['sentidos'] if t['sentidos'] else '',
                                                     'Defesas: ' + t['defesas_especiais'] if t['defesas_especiais'] else '',
                                                     'Deslocamento: ' + t['deslocamento']] if x),
              'charnotes': '%s — ND %s\n%s\nFonte: %s\n\n%s' % (t['nome'], t['nd'], t['tipo'], fonte, '\n'.join(t['texto'])),
              'oficionome': t['oficionome'], 'oficio2nome': '', 'divindade': '', 'modatributodefesa': 'des_mod', 'tamanho': str(tam),
              'deslocamento': (re.search(r'(\d+)m', t['deslocamento']) or re.search('(9)', '9')).group(1),
              'cdatributo': '@{int_mod} + @{condicaopermental}', 'cdequips': '0', 'cdpoderes': '0',
              'cdoutros': str(t['spellcd'] - 10 - h - m['int']) if t['spellcd'] else '0', 'extraslot': '0'})
    for k in 'rolltemp ataquetemp periciatemp resistemp danotemp fortemp destemp contemp inttemp sabtemp cartemp'.split(): d[k] = '0'
    for k in CONDS: d[k] = '0'
    # A aba de ameaça só mostra perícias com _treinada=1 (Fort/Ref/Von/Iniciativa/Percepção aparecem sempre).
    # bonus_treino da ficha: 2 / 4 (nível 7+) / 6 (nível 15+), calculado com parseInt(charnivel).
    try: lvl = int(t['charnivel'])
    except ValueError: lvl = 0
    treino = 6 if lvl >= 15 else 4 if lvl >= 7 else 2
    sempre = ('fortitude', 'reflexos', 'vontade', 'iniciativa', 'percepcao')
    for s, at in ATTR_OF.items():
        tr = 1 if (s in sk and s not in sempre) else 0
        d[s + '_treinada'] = str(tr); d[s + 'atributo2'] = SKF[at]
        d[s + 'outros'] = str(sk[s] - h - m[at] - tr * treino) if s in sk else '0'
    d['tamanho'] = '0'   # a ficha soma @{tamanho} só na Furtividade do jogador e não na da ameaça: o tamanho fica no texto do tipo
    sg = lambda v: ('+%d' % v) if v > 0 else str(v)
    tes = re.search(r'Tesouro\s+(.*)$', t['tesouro'] or t['equipamento'] or '')
    d.update({'cstype': '1', 'menace_name': t['nome'], 'menace_nd': t['nd'], 'menace_type_size': '%s (%s)' % (t['tipo'], papel),
              'menace_perception': t['sentidos'], 'menace_resist': t['defesas_especiais'], 'menace_desloc': t['deslocamento'],
              'menace_treasures': tes.group(1).strip() if tes else '', 'menace_hp': str(t['pv']), 'menace_mp': str(t['pm']),
              'menace_defense': str(t['defesa']), 'vida_max': str(t['pv']), 'mana_max': str(t['pm']),
              'menace_init': sg(sk.get('iniciativa', 0)), 'menace_percep': sg(sk.get('percepcao', 0)), 'menace_fortitude': sg(sk['fortitude']),
              'menace_reflex': sg(sk['reflexos']), 'menace_will': sg(sk['vontade'])})
    for k in m: d['menace_' + k] = str(m[k])
    for s, at in ATTR_OF.items():
        if s in ('fortitude', 'reflexos', 'vontade', 'iniciativa', 'percepcao', 'luta', 'pontaria', 'oficio2'): continue
        d['menace_%stotal' % s] = sg(sk.get(s, h + m[at]))
    d['attacks'] = t['attacks']; d['abilities'] = t['abilities']; d['powers'] = []; d['spells1'] = t['spells']
    for i in range(2, 6): d['spells%d' % i] = []
    d['extraSkills'] = []; eq = []
    etxt = re.split(r'\s*Tesouro\b', re.sub(r'^Equipamento\s*', '', t['equipamento']))[0].strip(' .')
    for it in (re.split(r',\s*(?![^()]*\))', etxt) if etxt else []):
        it = it.strip(' .')
        if not it: continue
        q = re.search(r'\s+x(\d+)$', it); n = int(q.group(1)) if q else 1
        if q: it = it[:q.start()]
        eq.append({'equipname': it[0].upper() + it[1:], 'equipquantity': str(n), 'equipslot': '0', 'equipweight': '0', 'sobrevivencia_treinada': '0'})
    d['equipments'] = eq
    meta = {'nome': t['nome'], 'nd': t['nd'], 'fonte': t['src'], 'fonte_label': label, 'pagina': t['pagina'], 'tipo': t['tipo'],
            'papel': papel.replace(', ', ' · '), 'pv': t['pv'], 'pm': t['pm'], 'defesa': t['defesa']}
    return {'meta': meta, 'sheet': d}

# ---------------------------------------------------------------- main
def main(cfg_path):
    cfg = json.load(open(cfg_path)); out = cfg.get('out_dir', 'saida'); os.makedirs(out + '/json', exist_ok=True)
    labels = {s['id']: s['label'] for s in cfg['sources']}
    entries, threats, problems = [], [], []
    for s in cfg['sources']:
        L = stream(s['path']); bl = blocks(L, s)
        for b in bl:   # continuação de blocos quebrados por diagramação (regiões indicadas no config)
            key = '%s:%s:%s' % (b['src'], b['page'], b['nome'])
            regs = cfg.get('entries_append', {}).get(key, [])
            if key in cfg.get('entries_regions', {}):   # reconstrói o bloco só a partir das regiões dadas
                b['entries'], b['bolds'], regs = [], [], cfg['entries_regions'][key]
            for (pg, t0, t1, x0, x1) in regs:
                for x in sorted([x for x in L if x['p'] == pg and t0 <= x['top'] <= t1 and x0 <= x['x0'] <= x1 and not x['T']], key=lambda x: x['top']):
                    if x['b']: b['bolds'].append(x['b'])
                    if (x['b'] and x['b'].split()[0].rstrip(',') not in CONT) or x['t'].startswith('•') or not b['entries']: b['entries'].append(x['t'])
                    else: b['entries'][-1] = join(b['entries'][-1], x['t'])
        print(s['id'], len(bl), 'blocos', file=sys.stderr)
        for b in bl:
            if not re.search(r'\d', b['entries'][0]): continue   # quadros-exemplo sem números (ex.: "Elemental", "Golem")
            b['text_fix'] = cfg.get('text_fix', {}).get('%s:%s:%s' % (b['src'], b['page'], b['nome']), [])
            b['nd_fix'] = cfg.get('nd_fix', {}); b['tipo_fix'] = cfg.get('tipo_fix', {})
            if '%s:%s:%s' % (b['src'], b['page'], b['nome']) in cfg.get('skip', []): continue
            ov = cfg.get('entries_override', {}).get('%s:%s:%s' % (b['src'], b['page'], b['nome']))
            if ov: b['entries'] = ov
            try: t = build(b, cfg.get('name_fix', {}))
            except Exception as e: problems.append('%s p.%s %s: %s' % (b['src'], b['page'], b['nome'], e)); continue
            if not t['nome'] or t['nd'] == '?' or not t['tipo'] or any(i.startswith('?') for i in t['icons']):
                problems.append('%s p.%s "%s" ND=%s tipo=%s ícones=%s' % (t['src'], t['pagina'], t['nome'], t['nd'], t['tipo'], t['icons']))
            threats.append(t); entries.append(sheet(t, labels[t['src']]))
    json.dump(threats, open(out + '/threats.json', 'w'), ensure_ascii=False, indent=1)
    with open(out + '/review.txt', 'w') as f:
        f.write('PROBLEMAS:\n' + '\n'.join(problems) + '\n\n')
        for n, t in enumerate(threats):
            f.write('=== #%d %s p%d ND %s | %s | %s | %s\n' % (n, t['src'], t['pagina'], t['nd'], t['nome'], t['tipo'], t['icons']))
            for e in t['texto']: f.write('  - ' + e[:120] + '\n')
    for e in entries:
        slug = re.sub(r'[^a-z0-9]+', '-', norm(e['meta']['nome'])).strip('-')
        json.dump(e['sheet'], open('%s/json/%s-%s.json' % (out, e['meta']['fonte'], slug), 'w'), ensure_ascii=False, indent=1)
    open(out + '/data.js', 'w').write('window.__T20_AMEACAS__ = ' + json.dumps(entries, ensure_ascii=False) + ';\n')
    print('%d fichas, %d problemas -> %s' % (len(entries), len(problems), out), file=sys.stderr)

if __name__ == '__main__': main(sys.argv[1])
