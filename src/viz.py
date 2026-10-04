"""Fungsi visualisasi proyek. Palet ramah buta warna: Okabe-Ito (kategori), viridis/cividis (kontinu)."""
import json, os, numpy as np, pandas as pd, yaml
import altair as alt, plotly.express as px, plotly.graph_objects as go
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans

import plotly.io as pio
pio.templates.default = "plotly_white"
alt.data_transformers.disable_max_rows()
CFG = yaml.safe_load(open("config.yaml", encoding="utf-8"))
VARS = CFG["variabel_multivariat"]
IDS = list(VARS)
LAB = {k: v["label"] for k, v in VARS.items()}
SUMBER = "Sumber: BPS, Susenas Maret 2024 – Rata-rata Konsumsi Perkapita Seminggu menurut Kab/Kota (satuan komoditas)"
OKABE = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00"]


def muat():
    """Baca data multivariat, hitung z-score, PCA (2 komponen), dan klaster k-means."""
    df = pd.read_csv("data/processed/kabkota_multivariat.csv")
    Z = StandardScaler().fit_transform(df[IDS])
    pca = PCA(n_components=2, random_state=1).fit(Z)
    sk = pca.transform(Z)
    df["PC1"], df["PC2"] = sk[:, 0], sk[:, 1]
    for i, c in enumerate(IDS):
        df["z_" + c] = Z[:, i]
    lab = KMeans(CFG["klaster_k"], n_init=20, random_state=1).fit_predict(Z)
    # urutkan nomor klaster menurut rata-rata PC1 agar stabil dan mudah dibaca
    urut = pd.Series(df.groupby(lab).PC1.mean()).rank().astype(int).to_dict()
    df["klaster"] = ["Klaster " + str(urut[l]) for l in lab]
    df.attrs["pca"] = pca
    return df


def loadings(df):
    p = df.attrs["pca"]
    return pd.DataFrame(p.components_.T, index=[LAB[c] for c in IDS], columns=["PC1", "PC2"]).round(3)


def multivariat(df):
    """PCA + parallel coordinates + heatmap klaster; brushing pada PCA menyorot garis di parallel coordinates."""
    ev = df.attrs["pca"].explained_variance_ratio_
    ks = sorted(df.klaster.unique())
    warna = alt.Scale(domain=ks, range=OKABE[:len(ks)])
    brush = alt.selection_interval(name="pilih", encodings=["x", "y"])
    tip = ["kabkota", "provinsi", "klaster"]

    scatter = (alt.Chart(df).mark_circle(size=42, opacity=.85).encode(
        x=alt.X("PC1:Q", title=f"PC1 ({ev[0]:.0%} varians)"), y=alt.Y("PC2:Q", title=f"PC2 ({ev[1]:.0%} varians)"),
        color=alt.condition(brush, alt.Color("klaster:N", scale=warna, title="Klaster"), alt.value("#cfcfcf")),
        tooltip=tip).add_params(brush).properties(width=300, height=280, title="Peta kab/kota di ruang PCA (seret untuk memilih)"))

    zc = ["z_" + c for c in IDS]
    base = alt.Chart(df).transform_fold(zc, as_=["v", "z"]).transform_calculate(
        variabel="replace(datum.v, 'z_', '')").transform_calculate(
        nama="datum.variabel")
    urutan = [LAB[c] for c in IDS]
    lab_expr = "{" + ",".join(f"'{c}':'{LAB[c]}'" for c in IDS) + "}[datum.variabel]"
    base = base.transform_calculate(label=lab_expr)
    enc = dict(x=alt.X("label:N", sort=urutan, title=None, axis=alt.Axis(labelAngle=-40)),
               y=alt.Y("z:Q", title="z-score konsumsi"), detail="kabkota:N")
    abu = base.mark_line(opacity=.05, color="#888").encode(**enc)
    sor = base.mark_line(opacity=.45).encode(**enc, color=alt.Color("klaster:N", scale=warna, legend=None),
                                              tooltip=tip).transform_filter(brush)
    par = (abu + sor).properties(width=620, height=250, title="Parallel coordinates (terseleksi = berwarna)")

    h = df.groupby("klaster")[zc].mean().reset_index().melt("klaster", var_name="v", value_name="z")
    h["variabel"] = h.v.str.replace("z_", "").map(LAB)
    heat = alt.Chart(h).mark_rect().encode(
        x=alt.X("variabel:N", sort=urutan, title=None, axis=alt.Axis(labelAngle=-40)), y=alt.Y("klaster:N", title=None),
        color=alt.Color("z:Q", scale=alt.Scale(scheme="purpleorange", domainMid=0), title="Rata-rata z"),
        tooltip=["klaster", "variabel", alt.Tooltip("z:Q", format=".2f")]).properties(width=300, height=150, title="Profil klaster (rata-rata z-score)")
    return ((scatter | heat).resolve_scale(color="independent") & par).configure(background="#fffaf0").configure_view(stroke=None).configure_title(fontSize=14, anchor="start")


def tampil(chart, tinggi=760):
    """Tampilkan chart Altair di <iframe> sendiri dengan pustaka vega tertanam (inline).
    Alasan: keluaran Altair bawaan memuat vega-embed lewat require.js milik Quarto dan sesekali gagal
    ('vegaEmbed is not a function', quarto-cli#10903). Di dalam iframe tidak ada require.js, dan tanpa CDN."""
    import html as _html
    doc = chart.to_html(inline=True)

    class _Html:                      # objek display sederhana (IPython.display.HTML memberi peringatan untuk iframe)
        def __init__(self, h): self.h = h
        def _repr_html_(self): return self.h
    return _Html(f'<iframe srcdoc="{_html.escape(doc, quote=True)}" title="Grafik interaktif" loading="lazy" '
                f'style="width:100%;height:{tinggi}px;border:0;background:transparent"></iframe>')


# ---------------------------------------------------------------- geospasial
def _gj():
    return json.load(open("data/processed/kabkota.geojson", encoding="utf-8"))


def _kelas(vals, k=5):
    """Kelas kuantil (0..k-1) + batas kelas. Kuantil dipilih karena sebaran konsumsi miring (banyak nilai kecil)."""
    s = pd.Series(vals)
    br = np.unique(np.quantile(s, np.linspace(0, 1, k + 1)))
    cls = np.clip(np.digitize(s, br[1:-1], right=True), 0, len(br) - 2)
    return cls, br


def peta_choropleth(df):
    """Peta 1 – choropleth kuantil 5 kelas; dropdown pilih komoditas; zoom/pan bawaan; layer batas provinsi (klik legenda)."""
    gj = _gj(); pv = json.load(open("data/processed/provinsi.geojson", encoding="utf-8"))
    d = df.set_index("kabkota").reindex([f["properties"]["kabkota"] for f in gj["features"]]).reset_index()
    pal = px.colors.sequential.Viridis
    pal = [pal[i] for i in (0, 2, 5, 7, 9)]
    cs = [[0, pal[0]], [.2, pal[0]], [.2, pal[1]], [.4, pal[1]], [.4, pal[2]], [.6, pal[2]], [.6, pal[3]], [.8, pal[3]], [.8, pal[4]], [1, pal[4]]]
    fig = go.Figure(); info = {}
    for c in IDS:
        cls, br = _kelas(d[c]); info[c] = (cls, br)
    c0 = IDS[0]
    def tt(br): return [f"{br[i]:.3g}–{br[i+1]:.3g}" for i in range(len(br) - 1)]
    fig.add_trace(go.Choropleth(geojson=gj, featureidkey="properties.kabkota", locations=d.kabkota, z=info[c0][0], zmin=-.5, zmax=4.5,
        colorscale=cs, marker_line_width=.2, marker_line_color="white", name="Kab/kota",
        customdata=np.c_[d.provinsi, d[c0]], hovertemplate="<b>%{location}</b><br>%{customdata[0]}<br>Konsumsi: %{customdata[1]:.3f}<extra></extra>",
        colorbar=dict(title="Kelas kuantil<br>(satuan/kapita/minggu)", tickvals=list(range(5)), ticktext=tt(info[c0][1]), len=.8)))
    fig.add_trace(go.Choropleth(geojson=pv, featureidkey="properties.provinsi", locations=[f["properties"]["provinsi"] for f in pv["features"]],
        z=[0] * len(pv["features"]), colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]], showscale=False, hoverinfo="skip",
        marker_line_width=1.1, marker_line_color="#222", name="Batas provinsi", showlegend=True))
    btn = [dict(label=LAB[c], method="update",
                args=[{"z": [info[c][0]], "customdata": [np.c_[d.provinsi, d[c]]], "colorbar.ticktext": [tt(info[c][1])]},
                      {"title.text": f"Konsumsi {LAB[c]} per kapita seminggu, kab/kota 2024"}, [0]]) for c in IDS]   # [0] = hanya trace kab/kota
    fig.update_layout(title=dict(text=f"Konsumsi {LAB[c0]} per kapita seminggu, kab/kota 2024", x=0.01, y=0.97, yanchor="top"),
        updatemenus=[dict(buttons=btn, x=0.01, y=0.88, xanchor="left", yanchor="top", direction="down", pad=dict(l=0, t=0))],
        geo=dict(fitbounds="locations", visible=False, projection_type="mercator"), margin=dict(l=0, r=0, t=60, b=70), height=560,
        legend=dict(orientation="h", x=1, xanchor="right", y=-0.02, yanchor="top"),
        annotations=[dict(text=SUMBER, x=0, y=-0.1, xref="paper", yref="paper", xanchor="left", showarrow=False, font=dict(size=10))])
    return fig


def peta_simbol(df):
    """Peta 2 – simbol proporsional (luas lingkaran ∝ nilai) di atas dasar abu-abu; dropdown pilih komoditas."""
    gj = _gj()
    d = df.set_index("kabkota").reindex([f["properties"]["kabkota"] for f in gj["features"]]).reset_index()
    ll = pd.DataFrame([f["properties"] for f in gj["features"]]).set_index("kabkota")
    d["lon"], d["lat"] = ll.loc[d.kabkota, "lon"].values, ll.loc[d.kabkota, "lat"].values
    fig = go.Figure(go.Choropleth(geojson=gj, featureidkey="properties.kabkota", locations=d.kabkota, z=[0] * len(d),
        colorscale=[[0, "#eeeeee"], [1, "#eeeeee"]], showscale=False, marker_line_width=.2, marker_line_color="white", hoverinfo="skip", name="Dasar"))
    def sz(c): v = d[c].clip(lower=0); return 2 + 16 * np.sqrt(v / v.max())   # luas ∝ nilai
    c0 = IDS[0]
    fig.add_trace(go.Scattergeo(lon=d.lon, lat=d.lat, mode="markers", name="Simbol",
        marker=dict(size=sz(c0), color="#0072B2", opacity=.5, line=dict(width=.4, color="white")),
        customdata=np.c_[d.kabkota, d.provinsi, d[c0]], hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<br>Konsumsi: %{customdata[2]:.3f}<extra></extra>"))
    btn = [dict(label=LAB[c], method="update",
                args=[{"marker.size": [sz(c)], "customdata": [np.c_[d.kabkota, d.provinsi, d[c]]]},
                      {"title.text": f"Simbol proporsional: {LAB[c]} per kapita seminggu, kab/kota 2024"}, [1]]) for c in IDS]   # [1] = trace simbol
    fig.update_layout(title=dict(text=f"Simbol proporsional: {LAB[c0]} per kapita seminggu, kab/kota 2024", x=0.01, y=0.97, yanchor="top"),
        updatemenus=[dict(buttons=btn, x=0.01, y=0.88, xanchor="left", yanchor="top")],
        geo=dict(fitbounds="locations", visible=False), margin=dict(l=0, r=0, t=60, b=70), height=560, showlegend=False,
        annotations=[dict(text=SUMBER + " | luas lingkaran sebanding dengan nilai", x=0, y=-0.1, xref="paper", yref="paper", xanchor="left", showarrow=False, font=dict(size=10))])
    return fig


# ---------------------------------------------------------------- hierarki
def _hier(df, warna):
    d = df.copy(); d["Indonesia"] = "Indonesia"
    pf = CFG["penduduk_file"]
    if os.path.exists(pf):
        p = pd.read_csv(pf); d = d.merge(p[["kabkota", "penduduk"]], on="kabkota", how="left")
        if d.penduduk.isna().any(): print("PERINGATAN: penduduk kosong untuk", d[d.penduduk.isna()].kabkota.tolist()[:5])
    else:
        d["penduduk"] = 1
        print("PERINGATAN: file penduduk tidak ada -> ukuran blok = 1 per kab/kota (hanya untuk uji coba)")
    d["z"] = d["z_" + warna]
    return d


def _satu(d, v, kind):
    kw = dict(path=["Indonesia", "pulau", "provinsi", "kabkota"], values="penduduk", color="z_" + v, color_continuous_scale="Cividis",
              range_color=[-2, 2], labels={"z_" + v: "z-score", "pulau": "Pulau", "provinsi": "Provinsi", "kabkota": "Kab/kota"})
    return (px.treemap if kind == "treemap" else px.sunburst)(d, **kw)


def hierarki(df):
    """Treemap + sunburst: Indonesia > Pulau > Provinsi > Kab/kota. Ukuran = penduduk; warna = z-score konsumsi.
    Satu dropdown memilih komoditas (hanya warna yang berubah). Mengembalikan (treemap, sunburst)."""
    d = _hier(df, IDS[0]); out = []
    for kind in ("treemap", "sunburst"):
        figs = {v: _satu(d, v, kind) for v in IDS}
        f = figs[IDS[0]]
        ids0 = list(f.data[0].ids)
        assert all(list(figs[v].data[0].ids) == ids0 for v in IDS), "urutan node berbeda"
        judul = lambda v: f"{LAB[v]}: ukuran = penduduk, warna = z-score konsumsi"
        btn = [dict(label=LAB[v], method="update", args=[{"marker.colors": [np.asarray(figs[v].data[0].marker.colors, float).tolist()]},
                                                         {"title.text": judul(v)}, [0]]) for v in IDS]
        f.update_traces(hovertemplate="<b>%{label}</b><br>Penduduk: %{value:,.0f}<br>z-score: %{color:.2f}<extra></extra>")
        f.update_layout(title=dict(text=judul(IDS[0]), x=0.01, y=0.98, yanchor="top"),
                        updatemenus=[dict(buttons=btn, x=0.01, y=1.0, xanchor="left", yanchor="bottom")],
                        margin=dict(l=0, r=0, t=100, b=50), height=560,
                        annotations=[dict(text=SUMBER, x=0, y=-0.06, xref="paper", yref="paper", xanchor="left", showarrow=False, font=dict(size=10))])
        if kind == "treemap": f.update_traces(pathbar=dict(visible=True))      # breadcrumb
        out.append(f)
    return tuple(out)