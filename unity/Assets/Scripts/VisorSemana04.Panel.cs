/*
================================================================
  VisorSemana04.Panel.cs   (parte de VisorSemana04)
================================================================
  El texto que se suma al panel de VisorQA al seleccionar una barra, y
  los controles de la seccion "Semana 4" de ese panel.

  El texto contesta lo que pide la semana para la barra seleccionada:
  ID, nodos, seccion, material, ejes locales (esos ya los escribe
  VisorQA), restricciones, N, Vy, Vz, T, My, Mz del caso activo,
  demanda-capacidad y la cadena de trazabilidad.

  FORMATO INVARIANTE: en un Windows en espanol, 0.5 saldria "0,5" y
  los numeros no se podrian comparar a simple vista con los que
  imprime semana04/trazabilidad.py, que usa punto.

  ACCIONES DIFERIDAS: cambiar de caso dispara la deformada y el redibujo
  de VisorQA. Hacerlo dentro de OnGUI cambia la cantidad de controles
  entre el evento de Layout y el de Repaint, y IMGUI lo reclama. Por eso
  los botones anotan la accion y se ejecuta en LateUpdate.
================================================================
*/

using System.Globalization;
using System.Text;
using UnityEngine;

public partial class VisorSemana04
{
    private System.Action accionPendiente;

    void Diferir(System.Action accion) { accionPendiente += accion; }

    void LateUpdate()
    {
        if (accionPendiente == null) return;
        System.Action a = accionPendiente;
        accionPendiente = null;
        a();
    }

    static string F(float v, string formato)
    {
        return v.ToString(formato, CultureInfo.InvariantCulture);
    }

    static string Cientifico(float v)
    {
        return v.ToString("0.000e+00", CultureInfo.InvariantCulture);
    }

    static string TextoRestr(int[] r)
    {
        if (r == null || r.Length < 6) return "[- - - - - -]";
        return $"[{r[0]} {r[1]} {r[2]} {r[3]} {r[4]} {r[5]}]";
    }

    /// Cuales de N, Vy, Vz, T, My, Mz mandan en cada tipo de barra. En un
    /// muro, el momento de su plano lo dice el JSON (el de inercia mayor)
    /// y el corte que lo acompana: Vz con My, Vy con Mz.
    static bool[] Relevantes(ElementoS4 e)
    {
        string t = e.tipo ?? "";
        if (e.es_brazo_rigido) return new[] { false, false, false, false, false, false };
        if (t.StartsWith("viga")) return new[] { false, true, true, false, true, true };
        if (t == "muro")
            return e.momento_en_el_plano == "My"
                ? new[] { true, false, true, false, true, false }
                : new[] { true, true, false, false, false, true };
        return new[] { true, false, false, false, true, true };
    }

    // ============================================================
    // TEXTO DEL PANEL
    // ============================================================
    public string DescribirElemento(int id)
    {
        var sb = new StringBuilder();
        sb.AppendLine("=========== SEMANA 4 ===========");
        if (!string.IsNullOrEmpty(Aviso)) sb.AppendLine("AVISO: " + Aviso);
        if (Anexo == null) return sb.ToString();

        ElementoS4 e = ElementoPorId(id);
        if (e == null)
        {
            sb.AppendLine($"(el elemento {id} no esta en el anexo)");
            return sb.ToString();
        }

        sb.AppendLine("--- material ---");
        sb.AppendLine(e.material);
        if (e.fpc_MPa > 0f) sb.AppendLine($"f'c    {F(e.fpc_MPa, "0.0")} MPa");
        sb.AppendLine($"E      {F(e.E_kPa / 1000f, "0")} MPa    G  {F(e.G_kPa / 1000f, "0")} MPa");
        sb.AppendLine($"nu     {F(e.poisson, "0.00")}     gamma  {F(e.gamma, "0.0")} kN/m3");

        sb.AppendLine("--- seccion ---");
        sb.AppendLine($"{e.seccion}   b {F(e.b, "0.00")} m   h {F(e.h, "0.00")} m   L {F(e.L, "0.000")} m");
        sb.AppendLine($"A  {F(e.A, "0.0000")} m2    J  {Cientifico(e.J)} m4");
        // En vigas y columnas Iz = b*h^3/12; en un muro la que importa es
        // la de su plano, y cual es lo dice el JSON.
        string rotuloI = e.tipo == "muro" && !string.IsNullOrEmpty(e.momento_en_el_plano)
            ? $"(la del plano: I{(e.momento_en_el_plano == "My" ? "y" : "z")}, momento {e.momento_en_el_plano})"
            : "(Iz = b*h^3/12)";
        sb.AppendLine($"Iy {Cientifico(e.Iy)} m4   Iz {Cientifico(e.Iz)} m4 {rotuloI}");

        sb.AppendLine("--- condiciones  [ux uy uz rx ry rz] ---");
        sb.AppendLine($"nodo {e.n1}  {TextoRestr(e.restr_n1)}"
                      + (e.diafragma_n1 >= 0 ? $"  diafragma, maestro {e.diafragma_n1}" : ""));
        sb.AppendLine($"nodo {e.n2}  {TextoRestr(e.restr_n2)}"
                      + (e.diafragma_n2 >= 0 ? $"  diafragma, maestro {e.diafragma_n2}" : ""));
        if (e.es_brazo_rigido)
            sb.AppendLine("brazo rigido: artificio numerico del muro; no se disena con esto");
        if (!string.IsNullOrEmpty(e.condiciones)) sb.AppendLine(e.condiciones);

        EsfuerzosS4 s = EsfuerzosDe(id);
        CasoS4 caso = CasoActivo();
        sb.AppendLine($"--- esfuerzos, caso activo {casoActivo} ---");
        if (caso != null) sb.AppendLine(caso.descripcion);
        if (s == null || s.f == null || s.f.Length < 12)
        {
            sb.AppendLine("(sin esfuerzos en este caso)");
        }
        else
        {
            // Internos, convencion de cara positiva: los extremos de las
            // estaciones del JSON. N positivo es traccion.
            string[] nombres = { "N", "Vy", "Vz", "T", "My", "Mz" };
            string[] unidades = { "kN", "kN", "kN", "kN*m", "kN*m", "kN*m" };
            bool[] manda = Relevantes(e);
            sb.AppendLine("               extremo i     extremo j");
            for (int k = 0; k < 6; k++)
            {
                float[] v = Magnitud(s, nombres[k]);
                float vi = (v != null && v.Length > 0) ? v[0] : 0f;
                float vj = (v != null && v.Length > 0) ? v[v.Length - 1] : 0f;
                sb.AppendLine($"{(manda[k] ? "*" : " ")} {nombres[k],-2} {unidades[k],-4}  "
                              + $"{F(vi, "0.00"),12}  {F(vj, "0.00"),12}");
            }
            sb.AppendLine($"(ejes locales; * = los que mandan en {e.tipo})");
            Extremo(sb, s, "My");
            Extremo(sb, s, "Mz");
        }

        sb.AppendLine("--- demanda / capacidad ---");
        FamiliaPM fam = (e.familia >= 0 && Anexo.familias != null && e.familia < Anexo.familias.Count)
                        ? Anexo.familias[e.familia] : null;
        if (fam == null)
        {
            sb.AppendLine("(sin enfierradura: no tiene curva P-M)");
        }
        else
        {
            DemandaS4 d = DemandaDe(id, casoActivo);
            sb.AppendLine($"familia {fam.indice}: {fam.clave}");
            if (d != null)
            {
                string cual = e.tipo == "muro" ? $" (|{e.momento_en_el_plano}|, en su plano)" : "";
                sb.AppendLine($"P {F(d.P, "0.0")} kN   M {F(d.M, "0.0")} kN*m{cual}   extremo {d.extremo}");
                sb.AppendLine(d.u >= 9999f
                    ? TextoFueraDeCurva(d, fam)
                    : $"Mn {F(d.Mn, "0.0")} kN*m   u {F(d.u, "0.000")}   {(d.pasa ? "PASA" : "NO PASA")}");
            }
        }

        sb.AppendLine("--- trazabilidad ---");
        sb.AppendLine("OpenSees    " + e.tag_opensees);
        GameObject go = visor != null ? visor.ObjetoDeElemento(id) : null;
        DatoElemento dato = go != null ? go.GetComponent<DatoElemento>() : null;
        if (go == null)
        {
            sb.AppendLine($"Unity       (la barra no esta dibujada: capa apagada) se espera \"{e.objeto_unity}\"");
        }
        else
        {
            // Se comprueba AHORA, sobre el objeto real de la escena: que se
            // llame como dice el JSON y que su DatoElemento tenga ese id.
            bool calza = go.name == e.objeto_unity && dato != null && dato.idElemento == id;
            sb.AppendLine($"Unity       GameObject \"{go.name}\"  DatoElemento.idElemento = "
                          + $"{(dato != null ? dato.idElemento.ToString() : "-")}  {(calza ? "OK" : "NO CALZA")}");
        }
        sb.AppendLine($"Resultados  semana04.json casos[{casoActivo}].esfuerzos[id={id}].f");
        sb.AppendLine($"            {e.resultados}");
        if (s != null && s.f != null && s.f.Length == 12)
        {
            sb.AppendLine("            f_i " + Vector6(s.f, 0));
            sb.AppendLine("            f_j " + Vector6(s.f, 6));
        }
        sb.AppendLine(fam != null
            ? $"Seccion     \"{e.seccion}\" -> familia P-M {fam.indice} ({fam.clave})"
            : $"Seccion     \"{e.seccion}\" (sin familia P-M)");
        sb.AppendLine(AnexoCalzaConElModelo
            ? "Modelo      nodos y seccion del anexo calzan con el modelo del visor: OK"
            : "Modelo      el anexo NO calza con el modelo del visor");
        return sb.ToString();
    }

    static void Extremo(StringBuilder sb, EsfuerzosS4 s, string m)
    {
        float[] v = Magnitud(s, m);
        if (v == null || s.x == null || v.Length != s.x.Length || v.Length == 0) return;
        int k = 0;
        for (int i = 1; i < v.Length; i++)
            if (Mathf.Abs(v[i]) > Mathf.Abs(v[k])) k = i;
        sb.AppendLine($"max |{m}| = {F(Mathf.Abs(v[k]), "0.00")} kN*m en x = {F(s.x[k], "0.00")} m"
                      + $"  ({v.Length} estaciones)");
    }

    static string Vector6(float[] f, int desde)
    {
        var sb = new StringBuilder("[");
        for (int k = 0; k < 6; k++)
            sb.Append((k > 0 ? "  " : "") + F(f[desde + k], "0.00"));
        return sb.Append("]").ToString();
    }

    // ============================================================
    // CONTROLES (dentro del scroll de VisorQA)
    // ============================================================
    public void DibujarControles()
    {
        GUILayout.Space(6);
        GUILayout.Label("--- Semana 4 ---");
        if (!string.IsNullOrEmpty(Aviso)) GUILayout.Label("AVISO: " + Aviso);
        if (Anexo == null) return;

        CasoS4 activo = CasoActivo();
        GUILayout.Label("Caso activo: " + casoActivo
                        + (activo != null ? "  =  " + activo.descripcion : ""));

        GUILayout.BeginHorizontal();
        foreach (CasoS4 c in Anexo.casos)
            if (c.tipo != "combinacion") BotonCaso(c);
        GUILayout.EndHorizontal();

        int n = 0;
        foreach (CasoS4 c in Anexo.casos)
        {
            if (c.tipo != "combinacion") continue;
            if (n % 2 == 0) GUILayout.BeginHorizontal();
            BotonCaso(c);
            if (n % 2 == 1) GUILayout.EndHorizontal();
            n++;
        }
        if (n % 2 == 1) GUILayout.EndHorizontal();

        bool diag = GUILayout.Toggle(mostrarDiagramas, "Diagramas de esfuerzos");
        if (diag != mostrarDiagramas) { mostrarDiagramas = diag; necesitaRedibujar = true; }
        if (mostrarDiagramas)
        {
            GUILayout.BeginHorizontal();
            foreach (string m in MAGNITUDES)
            {
                string elegida = m;
                if (GUILayout.Button((m == magnitud ? "> " : "") + m))
                {
                    magnitud = elegida;
                    necesitaRedibujar = true;
                }
            }
            GUILayout.EndHorizontal();

            GUILayout.BeginHorizontal();
            if (GUILayout.Button((soloSeleccionado ? "> " : "") + "la seleccionada"))
            { soloSeleccionado = true; necesitaRedibujar = true; }
            if (GUILayout.Button((!soloSeleccionado ? "> " : "") + "todas las visibles"))
            { soloSeleccionado = false; necesitaRedibujar = true; }
            GUILayout.EndHorizontal();

            GUILayout.Label($"escala del diagrama x{F(multiplicadorEscala, "0.0")} (solo grafica)");
            float esc = GUILayout.HorizontalSlider(multiplicadorEscala, 0.1f, 5f);
            if (!Mathf.Approximately(esc, multiplicadorEscala))
            { multiplicadorEscala = esc; necesitaRedibujar = true; }

            GUILayout.Label(LeyendaDiagrama());
            if (soloSeleccionado && Seleccionado < 0)
                GUILayout.Label("(click en una barra para ver su diagrama)");
        }

        bool pm = GUILayout.Toggle(mostrarPM, "Curva P-M de la seleccionada (ventana)");
        if (pm != mostrarPM) { mostrarPM = pm; texturaPMFirma = null; }

        int col = Anexo.info != null ? Anexo.info.columna_demo : -1;
        int mur = Anexo.info != null ? Anexo.info.muro_demo : -1;
        GUILayout.BeginHorizontal();
        if (col >= 0 && GUILayout.Button($"Columna demo ({col})")) Diferir(() => IrA(col));
        if (mur >= 0 && GUILayout.Button($"Muro demo ({mur})")) Diferir(() => IrA(mur));
        GUILayout.EndHorizontal();
    }

    void BotonCaso(CasoS4 c)
    {
        string nombre = c.nombre;
        if (GUILayout.Button((nombre == casoActivo ? "> " : "") + nombre))
            Diferir(() => ElegirCaso(nombre));
    }

    string LeyendaDiagrama()
    {
        string lado;
        switch (magnitud)
        {
            case "My": lado = "del lado traccionado: +My hacia +z local"; break;
            case "Mz": lado = "del lado traccionado: -Mz hacia +y local"; break;
            case "N": lado = "en z local; azul traccion, rojo compresion"; break;
            default: lado = "en " + (magnitud == "Vy" ? "y" : "z") + " local"; break;
        }
        string largo = F(largoDiagramaMaximo * multiplicadorEscala, "0.0");
        string u = UnidadDe(magnitud);
        string escala = "";
        if (mayorBarrasDibujado > 0f)
            escala += $"\n{largo} m = {F(mayorBarrasDibujado, "0.0")} {u} en vigas y columnas";
        if (mayorMurosDibujado > 0f)
            escala += $"\n{largo} m = {F(mayorMurosDibujado, "0.0")} {u} en muros (escala aparte)";
        return $"{magnitud} dibujado {lado}\nazul = {magnitud} > 0, rojo = {magnitud} < 0{escala}";
    }

    /// Selecciona la barra (en VisorQA, para que su panel la describa) y
    /// centra la camara en ella.
    void IrA(int id)
    {
        if (qa != null) qa.SeleccionarElemento(id);
        else Seleccionar(id);
        EnfocarElemento(id);
    }
}
