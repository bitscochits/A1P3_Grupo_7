/*
================================================================
  VisorSemana04.PM.cs   (parte de VisorSemana04)
================================================================
  La ventana con la curva P-M de la barra seleccionada y sus puntos
  de demanda, con el caso activo identificado en el titulo.

  La curva y los puntos vienen del JSON: la curva de
  capacidad.interaccion() sobre la seccion de fibras, y cada punto de
  demanda_capacidad.demanda() sobre los 12 de localForce. Aca solo se
  pintan.

  POR QUE UNA TEXTURA: IMGUI no dibuja lineas. Un Texture2D se pinta
  pixel a pixel y se regenera solo cuando cambia la seleccion o el
  caso activo, no en cada frame.

  EJES: M horizontal desde cero (la curva es de magnitudes) y P
  vertical con la compresion hacia arriba, como en el curso. Los
  limites incluyen TODAS las demandas de la barra, para que un punto
  fuera de la curva se vea fuera y no cortado en el borde.
================================================================
*/

using System.Text;
using UnityEngine;

public partial class VisorSemana04
{
    const int ANCHO_PM = 440;
    const int ALTO_PM = 300;

    public Color colorCurva = new Color(0.10f, 0.35f, 0.85f);
    public Color colorCurvaMax = new Color(0.65f, 0.75f, 0.95f);
    public Color colorDemanda = new Color(0.55f, 0.55f, 0.55f);
    public Color colorDemandaActiva = new Color(0.90f, 0.10f, 0.10f);

    private Rect ventanaPM;
    private bool ventanaIniciada = false;
    private Texture2D texturaPM;
    private string texturaPMFirma = null;
    private GUIStyle estiloSobreBlanco;

    // Limites del grafico en unidades del modelo (kN y kN*m).
    private float mMax = 1f, pMin = -1f, pMax = 1f;

    /// Hay ventana si hay algo que mostrar: una barra seleccionada que
    /// tiene familia P-M, y el toggle prendido.
    bool VentanaPMVisible()
    {
        if (!mostrarPM || Anexo == null || Anexo.familias == null || Seleccionado < 0) return false;
        ElementoS4 e = ElementoPorId(Seleccionado);
        return e != null && e.familia >= 0 && e.familia < Anexo.familias.Count;
    }

    void OnGUI()
    {
        if (!VentanaPMVisible()) return;
        if (!ventanaIniciada)
        {
            // Abajo, entre el panel izquierdo de VisorQA (430 px) y el del
            // editor, que ocupa la derecha. Se puede arrastrar.
            ventanaPM = new Rect(450f, Mathf.Max(10f, Screen.height - ALTO_PM - 200f),
                                 ANCHO_PM + 20f, ALTO_PM + 180f);
            ventanaIniciada = true;
        }
        ElementoS4 e = ElementoPorId(Seleccionado);
        GUI.color = Color.white;
        ventanaPM = GUI.Window(4404, ventanaPM, DibujarVentanaPM,
                               $"P-M  elemento {e.id} ({e.tipo})   caso activo: {casoActivo}");
    }

    void DibujarVentanaPM(int idVentana)
    {
        ElementoS4 e = ElementoPorId(Seleccionado);
        if (e == null || e.familia < 0 || e.familia >= Anexo.familias.Count) return;
        FamiliaPM fam = Anexo.familias[e.familia];

        if (GUI.Button(new Rect(ventanaPM.width - 26f, 2f, 22f, 16f), "x"))
            mostrarPM = false;

        if (estiloSobreBlanco == null)
        {
            estiloSobreBlanco = new GUIStyle(GUI.skin.label);
            estiloSobreBlanco.fontSize = 11;
            estiloSobreBlanco.normal.textColor = Color.black;
        }

        ActualizarTexturaPM(e, fam);
        Rect area = new Rect(10f, 22f, ANCHO_PM, ALTO_PM);
        if (texturaPM != null) GUI.DrawTexture(area, texturaPM);

        GUI.Label(new Rect(area.x + 3f, area.y + 1f, 220f, 16f),
                  $"P = {F(pMax, "0")} kN  (compresion +)", estiloSobreBlanco);
        GUI.Label(new Rect(area.x + 3f, area.yMax - 17f, 200f, 16f),
                  $"P = {F(pMin, "0")} kN", estiloSobreBlanco);
        GUI.Label(new Rect(area.xMax - 150f, area.yMax - 17f, 148f, 16f),
                  $"M = {F(mMax, "0")} kN*m", estiloSobreBlanco);

        DemandaS4 d = DemandaDe(e.id, casoActivo);
        var sb = new StringBuilder();
        sb.AppendLine($"familia {fam.indice}: {fam.tipo} {fam.seccion}  "
                      + $"{F(fam.b, "0.00")} x {F(fam.h, "0.00")} m   "
                      + $"As {F(fam.As_cm2, "0.0")} cm2 ({F(fam.cuantia_pct, "0.00")} %)");
        if (d == null)
        {
            sb.AppendLine("sin demanda en este caso");
        }
        else
        {
            sb.AppendLine($"{casoActivo}:  P = {F(d.P, "0.0")} kN   M = {F(d.M, "0.0")} kN*m"
                          + $"   (extremo {d.extremo})");
            sb.AppendLine(d.u >= 9999f
                ? TextoFueraDeCurva(d, fam)
                : $"Mn(P) = {F(d.Mn, "0.0")} kN*m   u = M/Mn = {F(d.u, "0.000")}   "
                  + (d.pasa ? "PASA" : "NO PASA"));
            if (fam.tipo == "muro")
                sb.AppendLine($"M = |{e.momento_en_el_plano}|, el de su plano.  Fuera de plano "
                              + $"{F(d.M_fuera_plano, "0.0")} kN*m (no se compara)");
        }
        sb.Append("azul: Mn nominal   celeste: M max del M-phi\n"
                  + "gris: los otros casos   rojo: el caso activo");
        GUI.Label(new Rect(10f, area.yMax + 4f, ANCHO_PM, 150f), sb.ToString());

        GUI.DragWindow(new Rect(0f, 0f, 10000f, 20f));
    }

    /// Un Mn = 0 no es "u infinito": es un P fuera del rango de la curva,
    /// y el caso real de este edificio son muros traccionados mas alla de
    /// su traccion pura bajo sismo. Se dice con palabras.
    static string TextoFueraDeCurva(DemandaS4 d, FamiliaPM fam)
    {
        float pmin = float.MaxValue, pmax = float.MinValue;
        if (fam.P != null)
            foreach (float p in fam.P) { pmin = Mathf.Min(pmin, p); pmax = Mathf.Max(pmax, p); }
        if (d.P < pmin)
            return $"P fuera de la curva: traccion {F(-d.P, "0")} kN mayor que la traccion "
                 + $"pura {F(-pmin, "0")} kN. NO PASA (u no definido)";
        if (d.P > pmax)
            return $"P fuera de la curva: compresion {F(d.P, "0")} kN mayor que la "
                 + $"compresion pura {F(pmax, "0")} kN. NO PASA (u no definido)";
        return "Mn = 0 a este P: NO PASA (u no definido)";
    }

    void ActualizarTexturaPM(ElementoS4 e, FamiliaPM fam)
    {
        string firma = e.id + "|" + casoActivo;
        if (texturaPM != null && firma == texturaPMFirma) return;
        texturaPMFirma = firma;
        if (texturaPM == null)
        {
            texturaPM = new Texture2D(ANCHO_PM, ALTO_PM, TextureFormat.RGBA32, false);
            texturaPM.filterMode = FilterMode.Bilinear;
            texturaPM.wrapMode = TextureWrapMode.Clamp;
        }

        mMax = 0f; pMin = 0f; pMax = 0f;
        int n = Mathf.Min(Largo(fam.P), Mathf.Min(Largo(fam.Mn), Largo(fam.Mmax)));
        for (int i = 0; i < n; i++)
        {
            mMax = Mathf.Max(mMax, Mathf.Max(fam.Mn[i], fam.Mmax[i]));
            pMin = Mathf.Min(pMin, fam.P[i]);
            pMax = Mathf.Max(pMax, fam.P[i]);
        }
        foreach (CasoS4 c in Anexo.casos)
        {
            DemandaS4 dc = DemandaDe(e.id, c.nombre);
            if (dc == null) continue;
            mMax = Mathf.Max(mMax, dc.M);
            pMin = Mathf.Min(pMin, dc.P);
            pMax = Mathf.Max(pMax, dc.P);
        }
        mMax = Mathf.Max(mMax, 1f) * 1.08f;
        float rango = Mathf.Max(pMax - pMin, 1f);
        pMin -= 0.06f * rango;
        pMax += 0.06f * rango;

        var px = new Color32[ANCHO_PM * ALTO_PM];
        var fondo = new Color32(255, 255, 255, 255);
        for (int i = 0; i < px.Length; i++) px[i] = fondo;

        var grilla = new Color32(228, 228, 228, 255);
        for (int g = 1; g < 4; g++)
        {
            int xg = XPx(mMax * g / 4f);
            LineaPx(px, xg, 0, xg, ALTO_PM - 1, grilla, 1);
            int yg = YPx(pMin + (pMax - pMin) * g / 4f);
            LineaPx(px, 0, yg, ANCHO_PM - 1, yg, grilla, 1);
        }
        var eje = new Color32(80, 80, 80, 255);
        LineaPx(px, 0, YPx(0f), ANCHO_PM - 1, YPx(0f), eje, 1);
        LineaPx(px, XPx(0f), 0, XPx(0f), ALTO_PM - 1, eje, 1);

        Polilinea(px, fam.P, fam.Mmax, n, colorCurvaMax, 1);
        Polilinea(px, fam.P, fam.Mn, n, colorCurva, 2);

        foreach (CasoS4 c in Anexo.casos)
        {
            if (c.nombre == casoActivo) continue;
            DemandaS4 dc = DemandaDe(e.id, c.nombre);
            if (dc != null) Punto(px, dc.M, dc.P, colorDemanda, 2);
        }
        DemandaS4 activa = DemandaDe(e.id, casoActivo);
        if (activa != null)
        {
            Punto(px, activa.M, activa.P, colorDemandaActiva, 4);
            Anillo(px, XPx(activa.M), YPx(activa.P), 7, new Color32(0, 0, 0, 255));
        }

        texturaPM.SetPixels32(px);
        texturaPM.Apply(false);
    }

    static int Largo(float[] v) { return v == null ? 0 : v.Length; }

    int XPx(float m)
    {
        return Mathf.Clamp(Mathf.RoundToInt(m / mMax * (ANCHO_PM - 1)), 0, ANCHO_PM - 1);
    }

    int YPx(float p)
    {
        return Mathf.Clamp(Mathf.RoundToInt((p - pMin) / (pMax - pMin) * (ALTO_PM - 1)),
                           0, ALTO_PM - 1);
    }

    void Polilinea(Color32[] px, float[] P, float[] M, int n, Color color, int grosor)
    {
        Color32 c = color;
        for (int i = 1; i < n; i++)
            LineaPx(px, XPx(M[i - 1]), YPx(P[i - 1]), XPx(M[i]), YPx(P[i]), c, grosor);
    }

    void Punto(Color32[] px, float m, float p, Color color, int radio)
    {
        Color32 c = color;
        int x = XPx(m), y = YPx(p);
        for (int j = -radio; j <= radio; j++)
            for (int i = -radio; i <= radio; i++)
                Pixel(px, x + i, y + j, c);
    }

    static void Anillo(Color32[] px, int x, int y, int r, Color32 c)
    {
        for (int k = -r; k <= r; k++)
        {
            Pixel(px, x + k, y - r, c); Pixel(px, x + k, y + r, c);
            Pixel(px, x - r, y + k, c); Pixel(px, x + r, y + k, c);
        }
    }

    /// Bresenham con pincel cuadrado para el grosor.
    static void LineaPx(Color32[] px, int x0, int y0, int x1, int y1, Color32 c, int grosor)
    {
        int dx = Mathf.Abs(x1 - x0), dy = -Mathf.Abs(y1 - y0);
        int sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1;
        int err = dx + dy;
        int r = grosor / 2;
        while (true)
        {
            for (int j = -r; j <= r; j++)
                for (int i = -r; i <= r; i++)
                    Pixel(px, x0 + i, y0 + j, c);
            if (x0 == x1 && y0 == y1) break;
            int e2 = 2 * err;
            if (e2 >= dy) { err += dy; x0 += sx; }
            if (e2 <= dx) { err += dx; y0 += sy; }
        }
    }

    static void Pixel(Color32[] px, int x, int y, Color32 c)
    {
        if (x < 0 || y < 0 || x >= ANCHO_PM || y >= ALTO_PM) return;
        px[y * ANCHO_PM + x] = c;
    }
}
