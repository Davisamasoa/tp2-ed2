#!/usr/bin/env python3
"""Gera docs/index.html: junta o modelo (docs/modelo.html) com o codigo-fonte do
projeto explicado linha por linha (explicacoes em docs/explicacoes/*.txt).

Uso: python3 docs/gerar_site.py   (a partir da raiz do repositorio)

Formato das explicacoes:
    = resumo do arquivo (pode ocupar varias linhas)
    30: explicacao da linha 30
    34-35: uma explicacao para as linhas 34 e 35
Linhas em branco, comentarios e chaves de fechamento recebem explicacao automatica.
Toda linha de codigo precisa de explicacao; o script avisa se faltar alguma.
"""
import html
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(RAIZ, 'docs')

ARQUIVOS = [
    ('Makefile', 'make'), ('registro.h', 'c'), ('main.c', 'c'),
    ('preparo.h', 'c'), ('preparo.c', 'c'),
    ('int2f.h', 'c'), ('int2f.c', 'c'),
    ('int_f1.h', 'c'), ('int_f1.c', 'c'),
    ('quicksort.h', 'c'), ('quicksort.c', 'c'),
    ('experimentos.sh', 'sh'),
]

PALAVRAS_C = set('''auto break case char const continue default do double else enum extern
float for goto if int long register return short signed sizeof static struct switch typedef
union unsigned void volatile while FILE NULL'''.split())


def inline(txt):
    """Formatacao simples nas explicacoes: `codigo` e **negrito**."""
    txt = html.escape(txt, quote=False)
    txt = re.sub(r'`([^`]+)`', r'<code>\1</code>', txt)
    txt = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', txt)
    return txt


def colorir_c(linha, em_comentario):
    """Realce de sintaxe minimo para C. Devolve (html, ainda_em_comentario)."""
    out, i, n = [], 0, len(linha)
    if em_comentario:
        fim = linha.find('*/')
        if fim < 0:
            return '<span class="cm">' + html.escape(linha) + '</span>', True
        out.append('<span class="cm">' + html.escape(linha[:fim + 2]) + '</span>')
        i = fim + 2
    while i < n:
        c = linha[i]
        if linha.startswith('//', i):
            out.append('<span class="cm">' + html.escape(linha[i:]) + '</span>')
            return ''.join(out), False
        if linha.startswith('/*', i):
            fim = linha.find('*/', i + 2)
            if fim < 0:
                out.append('<span class="cm">' + html.escape(linha[i:]) + '</span>')
                return ''.join(out), True
            out.append('<span class="cm">' + html.escape(linha[i:fim + 2]) + '</span>')
            i = fim + 2
            continue
        if c in '"\'':
            j = i + 1
            while j < n and linha[j] != c:
                j += 2 if linha[j] == '\\' else 1
            out.append('<span class="st">' + html.escape(linha[i:j + 1]) + '</span>')
            i = j + 1
            continue
        if c == '#' and linha[:i].strip() == '':
            m = re.match(r'#\s*\w+', linha[i:])
            out.append('<span class="pp">' + html.escape(m.group(0)) + '</span>')
            i += len(m.group(0))
            continue
        m = re.match(r'[A-Za-z_]\w*', linha[i:])
        if m:
            w = m.group(0)
            cls = 'kw' if w in PALAVRAS_C else ('ty' if w in ('Registro', 'TipoRegistro', 'Metricas', 'NoIntercalacao', 'NoF1', 'TipoArea') else ('mc' if w.isupper() and len(w) > 1 else ''))
            out.append(f'<span class="{cls}">{w}</span>' if cls else w)
            i += len(w)
            continue
        m = re.match(r'\d+(\.\d+)?([eE]\d+)?[LlFf]?', linha[i:])
        if m:
            out.append('<span class="nu">' + m.group(0) + '</span>')
            i += len(m.group(0))
            continue
        out.append(html.escape(c))
        i += 1
    return ''.join(out), False


def colorir_hash(linha):
    """Realce para Makefile e shell: comentarios com #."""
    if linha.lstrip().startswith('#') and not linha.startswith('#!'):
        return '<span class="cm">' + html.escape(linha) + '</span>'
    return html.escape(linha)


def classificar_c(linhas):
    """Para cada linha: 'vazia', 'comentario', 'fecha' (so chaves) ou 'codigo'.
    Tambem devolve, para as linhas 'fecha', o que esta sendo fechado."""
    tipos, fechamentos, pilha, em_com = [], {}, [], False
    for num, linha in enumerate(linhas, 1):
        # remove comentarios e strings para analisar a estrutura
        s, i, limpa = linha, 0, []
        while i < len(s):
            if em_com:
                f = s.find('*/', i)
                if f < 0:
                    i = len(s)
                    break
                em_com, i = False, f + 2
                continue
            if s.startswith('//', i):
                break
            if s.startswith('/*', i):
                em_com, i = True, i + 2
                continue
            if s[i] in '"\'':
                q, j = s[i], i + 1
                while j < len(s) and s[j] != q:
                    j += 2 if s[j] == '\\' else 1
                limpa.append('""')
                i = j + 1
                continue
            limpa.append(s[i])
            i += 1
        cod = ''.join(limpa).strip()
        if not linha.strip():
            tipos.append('vazia')
        elif not cod:
            tipos.append('comentario')
        elif re.fullmatch(r'[{}]+;?', cod):
            tipos.append('fecha')
        else:
            tipos.append('codigo')
        # pilha de blocos abertos (para explicar as chaves de fechamento)
        for ch in cod:
            if ch == '{':
                pilha.append((num, rotulo_bloco(cod, linhas, num)))
            elif ch == '}' and pilha:
                aberto = pilha.pop()
                if tipos[-1] == 'fecha':
                    fechamentos.setdefault(num, []).append(aberto)
    return tipos, fechamentos


def rotulo_bloco(cod, linhas, num):
    """Nome do bloco aberto na linha num (while, if, funcao...)."""
    alvo = cod
    if cod.startswith('{') or re.match(r'^}\s*else', cod):
        alvo = cod
    for kw, nome in (('else if', 'do `else if`'), ('else', 'do `else`'), ('while', 'do laço `while`'),
                     ('for', 'do laço `for`'), ('if', 'do `if`'), ('switch', 'do `switch`'),
                     ('typedef struct', 'da `struct`'), ('union', 'da `union`'), ('struct', 'da `struct`')):
        if re.search(r'(^|[}\s])' + kw + r'\b', alvo):
            return nome
    m = re.match(r'.*?\b(\w+)\s*\(', alvo)
    if m:
        return f'da função `{m.group(1)}`'
    if '=' in alvo:
        return 'da inicialização'
    return 'do bloco'


def explicacao_fecha(num, fechos):
    if not fechos:
        return 'Fecha o bloco aberto acima.'
    partes = [f'{rot} (aberto na linha {ini})' for ini, rot in reversed(fechos)]
    return 'Fecha o bloco ' + ' e '.join(partes) + '.'


def ler_explicacoes(nome):
    caminho = os.path.join(DOCS, 'explicacoes', nome + '.txt')
    resumo, exps, atual = [], {}, None
    with open(caminho, encoding='utf-8') as f:
        for bruto in f:
            linha = bruto.rstrip('\n')
            m = re.match(r'^(\d+)(?:-(\d+))?:\s?(.*)$', linha)
            if m:
                ini = int(m.group(1))
                fim = int(m.group(2) or ini)
                atual = [ini, fim, m.group(3)]
                if ini in exps:
                    sys.exit(f'{nome}: linha {ini} explicada duas vezes')
                exps[ini] = atual
            elif linha.startswith('='):
                atual = None
                resumo.append(linha[1:].strip())
            elif linha.strip() and atual is not None:
                atual[2] += ' ' + linha.strip()
            elif linha.strip() and resumo:
                resumo.append(linha.strip())
    return ' '.join(resumo), exps


def gerar_arquivo(nome, lang):
    with open(os.path.join(RAIZ, nome), encoding='utf-8') as f:
        linhas = f.read().split('\n')
    if linhas and linhas[-1] == '':
        linhas.pop()
    resumo, exps = ler_explicacoes(nome)

    if lang == 'c':
        tipos, fechos = classificar_c(linhas)
    else:
        tipos, fechos = [], {}
        for l in linhas:
            t = l.strip()
            tipos.append('vazia' if not t else ('comentario' if t.startswith('#') and not t.startswith('#!') else 'codigo'))

    # mapa linha -> (inicio do grupo, fim do grupo, texto)
    cobre = {}
    for ini, (a, b, txt) in exps.items():
        for k in range(a, b + 1):
            if k in cobre:
                sys.exit(f'{nome}: linha {k} coberta duas vezes')
            cobre[k] = (a, b, txt)
    faltando = [i + 1 for i, t in enumerate(tipos) if t == 'codigo' and (i + 1) not in cobre]
    if faltando:
        sys.exit(f'{nome}: faltam explicacoes para as linhas {faltando}')
    fora = [k for k in cobre if k > len(linhas)]
    if fora:
        sys.exit(f'{nome}: explicacoes para linhas inexistentes {fora}')

    linhas_html, em_com = [], False
    for l in linhas:
        if lang == 'c':
            h, em_com = colorir_c(l, em_com)
        else:
            h = colorir_hash(l)
        linhas_html.append(h)

    # agrupa comentarios consecutivos numa so explicacao
    linhas_tab, i = [], 0
    while i < len(linhas):
        num = i + 1
        if num in cobre:
            a, b, txt = cobre[num]
            linhas_tab.append((num, b - num + 1, 'exp', inline(txt)))
            i = b
            continue
        t = tipos[i]
        if t == 'comentario':
            j = i
            while j + 1 < len(linhas) and tipos[j + 1] == 'comentario' and (j + 2) not in cobre:
                j += 1
            qtd = j - i + 1
            txt = ('Comentário: texto para quem lê o código. O compilador ignora '
                   + ('estas linhas.' if qtd > 1 else 'esta linha.'))
            linhas_tab.append((num, qtd, 'com', txt))
            i = j + 1
            continue
        if t == 'fecha':
            linhas_tab.append((num, 1, 'auto', inline(explicacao_fecha(num, fechos.get(num)))))
        else:
            linhas_tab.append((num, 1, 'vazia', ''))
        i += 1

    partes = []
    for num, span, cls, txt in linhas_tab:
        for k in range(num, num + span):
            cel = ''
            if k == num:
                rs = f' rowspan="{span}"' if span > 1 else ''
                cel = f'<td class="ex {cls}"{rs}>{txt}</td>'
            partes.append(f'<tr id="{ancora(nome)}-L{k}"><td class="ln">{k}</td>'
                          f'<td class="co"><pre>{linhas_html[k - 1] or " "}</pre></td>{cel}</tr>')
    tabela = '\n'.join(partes)
    return (f'<section class="arquivo" id="{ancora(nome)}">\n<h3><code>{nome}</code></h3>\n'
            f'<p class="resumo">{inline(resumo)}</p>\n'
            f'<div class="tabela-rolagem"><table class="codigo">\n{tabela}\n</table></div>\n</section>')


def ancora(nome):
    return 'arq-' + re.sub(r'[^a-z0-9_]', '-', nome.lower())


def main():
    with open(os.path.join(DOCS, 'modelo.html'), encoding='utf-8') as f:
        modelo = f.read()
    indice = '\n'.join(f'<li><a href="#{ancora(n)}"><code>{n}</code></a></li>' for n, _ in ARQUIVOS)
    blocos = '\n'.join(gerar_arquivo(n, l) for n, l in ARQUIVOS)
    saida = modelo.replace('<!--INDICE_CODIGO-->', indice).replace('<!--CODIGO-->', blocos)
    if '—' in saida:
        sys.exit('o texto tem travessao; troque por virgula, dois-pontos ou parenteses')
    with open(os.path.join(DOCS, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(saida)
    print('docs/index.html gerado')


if __name__ == '__main__':
    main()
