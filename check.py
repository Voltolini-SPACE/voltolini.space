#!/usr/bin/env python3
"""Validação local do site voltolini.space (stdlib apenas, sem rede).

    python3 check.py          # valida e sai 0/1

Checa: assets existem, refs locais resolvem, OG absoluto e coerente,
acessibilidade básica, voz da marca (sem travessão no texto público),
sem segredos. Publicação continua sendo ato humano/CI.
"""
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
INDEX = RAIZ / "index.html"
PAGES = ["index.html", "404.html"]
ASSETS = ["assets/favicon.svg", "assets/og-image.png", "assets/foto-voltolini.svg",
          "assets/nomos-preview.png", "assets/fonts/fredoka.woff2",
          "assets/fonts/inter400.woff2", "assets/fonts/inter600.woff2",
          "assets/fonts/jbmono.woff2", "CNAME"]
BASE = "https://voltolini.space/"


class _P(HTMLParser):
    def __init__(self):
        super().__init__()
        self.metas, self.links, self.local_refs = [], [], []
        self.h1 = 0
        self.imgs_sem_alt = 0
        self.lang = None
        self.texto = []
        self.em_estilo = False

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "html":
            self.lang = d.get("lang")
        if tag == "h1":
            self.h1 += 1
        if tag == "meta":
            self.metas.append(d)
        if tag == "link":
            self.links.append(d)
        if tag in ("style", "script"):
            self.em_estilo = True
        if tag == "img" and not d.get("alt"):
            self.imgs_sem_alt += 1
        for a in ("href", "src"):
            v = d.get(a)
            if v and not v.startswith(("http://", "https://", "#", "mailto:", "data:")):
                self.local_refs.append(v)

    def handle_endtag(self, tag):
        if tag in ("style", "script"):
            self.em_estilo = False

    def handle_data(self, data):
        if not self.em_estilo:
            self.texto.append(data)


def main() -> int:
    erros = []

    for rel in ASSETS:
        p = RAIZ / rel
        if not p.exists() or p.stat().st_size == 0:
            erros.append(f"asset ausente/vazio: {rel}")

    for nome in PAGES:
        pg = RAIZ / nome
        if not pg.exists():
            erros.append(f"página ausente: {nome}")
            continue
        ex = _P()
        ex.feed(pg.read_text(encoding="utf-8"))
        for ref in ex.local_refs:
            if not (pg.parent / ref).exists():
                erros.append(f"{nome}: ref quebrada -> {ref}")
        if ex.imgs_sem_alt:
            erros.append(f"{nome}: {ex.imgs_sem_alt} <img> sem alt")
        if ex.lang != "pt-BR":
            erros.append(f"{nome}: <html> sem lang pt-BR")

    ex = _P()
    ex.feed(INDEX.read_text(encoding="utf-8"))
    props = {m.get("property"): m.get("content") for m in ex.metas}
    names = {m.get("name"): m.get("content") for m in ex.metas}
    canonical = [l["href"] for l in ex.links if "canonical" in (l.get("rel") or "")]

    if ex.h1 != 1:
        erros.append(f"index: deve ter exatamente 1 h1 (tem {ex.h1})")
    og_url, og_img = props.get("og:url"), props.get("og:image")
    tw_img = names.get("twitter:image")
    for rot, url in (("og:url", og_url), ("og:image", og_img), ("twitter:image", tw_img)):
        if not url or not url.startswith("https://"):
            erros.append(f"index: {rot} precisa ser absoluto https ({url!r})")
    if not canonical or canonical[0] != og_url:
        erros.append(f"index: canonical != og:url ({canonical} vs {og_url})")
    if og_url != BASE:
        erros.append(f"index: og:url fora da BASE ({og_url} != {BASE})")
    if og_img and not og_img.startswith(BASE):
        erros.append("index: og:image fora da base canônica")
    if tw_img != og_img:
        erros.append("index: twitter:image diverge de og:image")
    cname = (RAIZ / "CNAME").read_text().strip()
    if f"https://{cname}/" != BASE:
        erros.append(f"CNAME ({cname}) diverge da BASE ({BASE})")

    # og-image 1200x630 (header PNG)
    png = (RAIZ / "assets/og-image.png").read_bytes()
    if png[:8] != b"\x89PNG\r\n\x1a\n":
        erros.append("og-image.png inválido")
    else:
        w = int.from_bytes(png[16:20], "big")
        h = int.from_bytes(png[20:24], "big")
        if (w, h) != (1200, 630):
            erros.append(f"og-image {w}x{h}, esperado 1200x630")

    # voz da marca: sem travessão no texto público (regra 2)
    texto = "".join(ex.texto)
    if "—" in texto:
        erros.append("voz: travessão (—) no texto público; use ponto ou vírgula")

    # sem segredos
    bruto = INDEX.read_text(encoding="utf-8")
    for pat in ("sk-" + "live", "ghp_", "AKIA", "-----BEGIN", "xoxb-"):
        if pat in bruto:
            erros.append(f"possível segredo no index: {pat}")

    # contenção: aurora não pode virar scroll horizontal (lição H5.1)
    if "overflow-x:clip" not in bruto:
        erros.append("html sem overflow-x:clip (aurora vaza)")


    # ===== antirregressão v1.2 =====
    # tema: abre sempre escuro (decisão do dono 07/08)
    if "var _t = 'escuro';" not in bruto:
        erros.append("tema: boot não abre no escuro por padrão")
    # camada premium não pode sumir em silêncio
    for marca_premium in ('class="grao"', 'id="progresso"', 'orbe-a', 'orbe-b', 'orbe-c',
                          'class="contador"', 'ia-shimmer', "requestAnimationFrame(aurora)"):
        if marca_premium not in bruto:
            erros.append(f"premium: sumiu '{marca_premium}'")
    # tagline bilíngue
    for frase in ("aprender · ensinar · colaborar com ia", "learn · teach · collaborate with ai"):
        if frase not in bruto:
            erros.append(f"tagline: sumiu '{frase}'")
    # ecossistema completo
    for dominio in ("podpagar.com.br", "confrapag.com.br", "se7enpay.com.br",
                    "github.com/Voltolini-SPACE/NOMOS"):
        if dominio not in bruto:
            erros.append(f"ecossistema: sumiu {dominio}")
    # SE7EN PAY sempre em caixa alta com o 7 (regra da casa)
    for errado in ("Se7en Pay", "se7en pay", "Se7enPay", "SEVEN PAY"):
        if errado in bruto:
            erros.append(f"marca: grafia errada '{errado}' (é SE7EN PAY)")
    # runtime 100% local: nada que o browser baixe pode vir de fora
    for m in re.finditer(r'<(?:img|script)[^>]+src="(https?://[^"]+)"', bruto):
        erros.append(f"asset externo em runtime: {m.group(1)}")
    for m in re.finditer(r'<link[^>]+rel="(?:stylesheet|preload|icon|apple-touch-icon)"[^>]*href="(https?://[^"]+)"', bruto):
        erros.append(f"asset externo em runtime: {m.group(1)}")
    # gradiente-assinatura da marca presente
    if "linear-gradient(120deg,#FF7A4D,#3B6FE0)" not in bruto:
        erros.append("marca: gradiente-assinatura sumiu")


    # ===== antirregressão v1.3.4: proporção de imagens (incidente NOMOS) =====
    # 1. regra global obrigatória: largura responsiva exige altura automática
    if "img { max-width:100%; height:auto; }" not in bruto:
        erros.append("img: regra global 'max-width:100%; height:auto' sumiu (reintroduz deformação)")
    # 2. regra específica do shot do NOMOS
    if ".nomos .shot img { display:block; width:100%; height:auto; }" not in bruto:
        erros.append("nomos: regra .shot img com height:auto sumiu")
    # 3. atributos width/height de cada <img> devem bater com o arquivo real
    for m in re.finditer(r'<img[^>]*src="assets/([^"]+\.png)"[^>]*width="(\d+)"[^>]*height="(\d+)"', bruto):
        arq, aw, ah = m.group(1), int(m.group(2)), int(m.group(3))
        dados = (RAIZ / "assets" / arq).read_bytes()
        rw = int.from_bytes(dados[16:20], "big")
        rh = int.from_bytes(dados[20:24], "big")
        if abs(aw / ah - rw / rh) > 0.01:
            erros.append(f"{arq}: atributos {aw}x{ah} divergem do arquivo {rw}x{rh}")
    # 4. foto do quem sou tem height FIXA no CSS; o asset PRECISA ser quadrado
    svg = (RAIZ / "assets/foto-voltolini.svg").read_text()
    vb = re.search(r'viewBox="0 0 (\d+) (\d+)"', svg)
    if not vb or vb.group(1) != vb.group(2):
        erros.append("foto-voltolini.svg: viewBox não é quadrado; .quem img (180x180) deformaria")
    # 5. nenhuma NOVA regra de height fixa em px para seletores de img (allowlist: .quem img)
    for m in re.finditer(r'([^{}]*\bimg\b[^{}]*)\{([^}]*height:\s*\d+px[^}]*)\}', bruto):
        sel = m.group(1).strip()
        if ".quem img" not in sel:
            erros.append(f"img: height fixa em px no seletor '{sel}' (classe do incidente NOMOS)")

    print("voltolini.space · validação local\n")
    if erros:
        for e in erros:
            print(f"  x {e}")
        print(f"\nRESULTADO: INCONSISTENTE ({len(erros)} erro(s))")
        return 1
    print("  ok  assets, refs, OG absoluto/coerente, a11y, voz, sem segredos")
    print("\nRESULTADO: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
