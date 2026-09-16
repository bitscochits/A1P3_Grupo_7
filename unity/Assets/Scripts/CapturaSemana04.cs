/*
================================================================
  CapturaSemana04.cs
================================================================
  Saca capturas de la Semana 4 sin intervencion: para revisar el visor
  A LA VISTA -- un diagrama puede compilar, leer bien el JSON y aun
  asi dibujarse del lado equivocado -- y para el informe.

      build/LaboratorioEstructural.exe -capturarS4 <carpeta>
            -screen-width 1920 -screen-height 1080 -screen-fullscreen 0

  Sin ese argumento no hace nada: ni siquiera crea su objeto. Es una
  herramienta de verificacion, no parte del visor.

  Cada escena se arma con la MISMA API que usan los botones del panel
  (SeleccionarElemento, ElegirCaso, EnfocarElemento), asi que lo que
  se captura es lo que ve quien hace la demo. Junto a cada imagen deja
  el texto del panel de Semana 4, para cruzarlo con
  semana04/trazabilidad.py.

  Toca dos campos privados por reflexion -- el scroll del panel de
  VisorQA y el angulo de la camara -- solo para que la captura muestre
  la parte del panel que importa desde un angulo que se lea. No cambia
  nada del calculo.
================================================================
*/

using System.Collections;
using System.IO;
using System.Reflection;
using System.Text;
using UnityEngine;

public class CapturaSemana04 : MonoBehaviour
{
    private string carpeta;
    private readonly StringBuilder registro = new StringBuilder();

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void Arrancar()
    {
        string[] args = System.Environment.GetCommandLineArgs();
        for (int i = 0; i < args.Length - 1; i++)
        {
            if (args[i] != "-capturarS4") continue;
            var go = new GameObject("CapturaSemana04");
            go.AddComponent<CapturaSemana04>().carpeta = args[i + 1];
            return;
        }
    }

    IEnumerator Start()
    {
        Directory.CreateDirectory(carpeta);
        // Los visores cargan en su Start y esperan un frame: margen amplio.
        yield return new WaitForSeconds(5f);

        VisorQA qa = FindAnyObjectByType<VisorQA>();
        VisorSemana04 s4 = FindAnyObjectByType<VisorSemana04>();
        CamaraOrbital cam = FindAnyObjectByType<CamaraOrbital>();
        if (qa == null || s4 == null || cam == null || s4.Anexo == null)
        {
            File.WriteAllText(Path.Combine(carpeta, "ERROR.txt"),
                "falta VisorQA, VisorSemana04, CamaraOrbital o el anexo. Aviso: "
                + (s4 != null ? s4.Aviso : "(sin VisorSemana04)"));
            Application.Quit(2);
            yield break;
        }

        InfoSemana04 info = s4.Anexo.info;
        int col = info.columna_demo;
        int mur = info.muro_demo;
        registro.AppendLine("edificio " + info.edificio + "  caso por defecto " + info.caso_por_defecto);
        registro.AppendLine("aviso del anexo: '" + s4.Aviso + "'  calza con el modelo: " + s4.AnexoCalzaConElModelo);
        registro.AppendLine();

        Angulo(cam, 28f, 35f);
        // La lamina ampliada de la Semana 3 queda detras del panel: fuera.
        VisorSemana03 s3 = FindAnyObjectByType<VisorSemana03>();
        if (s3 != null && s3.jaulaDetalle) { s3.jaulaDetalle = false; s3.Redibujar(); }
        s4.mostrarDiagramas = true;
        s4.mostrarPM = true;
        s4.multiplicadorEscala = 1f;

        // 1. La columna demo: panel con material, esfuerzos, trazabilidad y P-M.
        s4.ElegirCaso(info.caso_por_defecto);
        s4.magnitud = "My";
        s4.soloSeleccionado = true;
        qa.SeleccionarElemento(col);
        s4.EnfocarElemento(col);
        Scroll(qa, 100000f);
        yield return Foto("01_columna_" + col + "_panel_y_PM", s4, col);

        // 2. Momento My de las vigas de un piso: el lado traccionado a la vista.
        s4.soloSeleccionado = false;
        s4.magnitud = "My";
        qa.soloNivel = 2;
        s4.Redibujar();
        EncuadrarNivel(qa, cam);
        Scroll(qa, 0f);
        yield return Foto("02_My_todas_piso_2", s4, -1);

        // 3. Una viga cargada con su parabola y sus etiquetas.
        int viga = VigaConParabola(s4, info.caso_por_defecto);
        if (viga >= 0)
        {
            s4.soloSeleccionado = true;
            qa.soloNivel = -1;
            qa.SeleccionarElemento(viga);
            s4.EnfocarElemento(viga);
            Angulo(cam, 12f, 20f);
            yield return Foto("03_viga_" + viga + "_My_etiquetas", s4, viga);
            Angulo(cam, 28f, 35f);
        }

        // 4. Axial N en todo el edificio: traccion y compresion por color.
        s4.soloSeleccionado = false;
        s4.magnitud = "N";
        qa.soloNivel = -1;
        s4.Redibujar();
        cam.EncuadrarTodo();
        yield return Foto("04_N_todas", s4, -1);

        // 4b. La carga repartida del mismo piso: la causa del diagrama.
        s4.magnitud = "wz";
        qa.soloNivel = 2;
        s4.Redibujar();
        EncuadrarNivel(qa, cam);
        yield return Foto("04b_wz_todas_piso_2", s4, -1);

        // 5. Corte Vz de un piso.
        s4.magnitud = "Vz";
        qa.soloNivel = 2;
        s4.Redibujar();
        EncuadrarNivel(qa, cam);
        yield return Foto("05_Vz_todas_piso_2", s4, -1);

        // 5b. Capas: areas tributarias y cargas G del mismo piso, sin diagramas.
        s4.mostrarDiagramas = false;
        s4.mostrarPM = false;
        s4.Redibujar();
        qa.verAreasTributarias = true;
        Refrescar(qa);
        if (s3 != null)
        {
            s3.mostrarCargas = true;
            s3.cargasConLaDeformada = false;
            s3.casoCarga = "G";
            s3.Redibujar();
        }
        yield return Foto("05b_capas_areas_y_cargas_G_piso_2", s4, -1);
        qa.verAreasTributarias = false;
        Refrescar(qa);
        if (s3 != null)
        {
            s3.cargasConLaDeformada = true;
            s3.casoCarga = "EX";
            s3.Redibujar();
        }
        s4.mostrarDiagramas = true;
        s4.mostrarPM = true;

        // 6. El muro demo con su P-M, en la combinacion con sismo en Y.
        s4.soloSeleccionado = true;
        s4.magnitud = EnSuPlano(s4, mur);
        qa.soloNivel = -1;
        s4.ElegirCaso("1.2G+1.0Q+1.4EY");
        qa.SeleccionarElemento(mur);
        s4.EnfocarElemento(mur);
        Scroll(qa, 100000f);
        yield return Foto("06_muro_" + mur + "_" + s4.magnitud + "_PM_1.2G+1.0Q+1.4EY", s4, mur);

        // 7 y 8. Los dos casos que no pasan, si existen en este edificio.
        if (s4.ElementoPorId(80) != null && info.edificio == "ingenieria")
        {
            s4.magnitud = "My";
            s4.ElegirCaso(info.caso_por_defecto);
            qa.SeleccionarElemento(80);
            s4.EnfocarElemento(80);
            yield return Foto("07_columna_80_no_pasa", s4, 80);
        }
        if (s4.ElementoPorId(427) != null && info.edificio == "ingenieria")
        {
            s4.magnitud = EnSuPlano(s4, 427);
            s4.ElegirCaso("1.2G+1.0Q+1.4EX");
            qa.SeleccionarElemento(427);
            s4.EnfocarElemento(427);
            yield return Foto("08_muro_427_fuera_de_curva", s4, 427);
        }
        if (s4.ElementoPorId(508) != null && info.edificio == "ingenieria")
        {
            // Un muro corto traccionado por el sismo en Y: no pasa en flexion.
            s4.magnitud = EnSuPlano(s4, 508);
            s4.ElegirCaso("1.2G+1.0Q+1.4EY");
            qa.SeleccionarElemento(508);
            s4.EnfocarElemento(508);
            yield return Foto("08b_muro_508_no_pasa_1.2G+1.0Q+1.4EY", s4, 508);
        }

        // 9. Deformada de una combinacion.
        s4.mostrarPM = false;
        s4.mostrarDiagramas = false;
        s4.ElegirCaso("1.2G+1.0Q+1.4EY");
        s4.AplicarDeformadaDelCaso();
        s4.Redibujar();
        cam.EncuadrarTodo();
        Scroll(qa, 0f);
        yield return Foto("09_deformada_1.2G+1.0Q+1.4EY", s4, -1);

        File.WriteAllText(Path.Combine(carpeta, "registro.txt"), registro.ToString());
        yield return new WaitForSeconds(0.5f);
        Application.Quit(0);
    }

    IEnumerator Foto(string nombre, VisorSemana04 s4, int id)
    {
        // Que se rehagan mallas, texturas y el OnGUI con el estado nuevo.
        yield return new WaitForSeconds(1.5f);
        string ruta = Path.Combine(carpeta, nombre + ".png");
        ScreenCapture.CaptureScreenshot(ruta);
        yield return new WaitForEndOfFrame();
        yield return new WaitForSeconds(1f);

        registro.AppendLine("=== " + nombre + " ===");
        registro.AppendLine($"caso {s4.casoActivo}  magnitud {s4.magnitud}  "
                            + $"solo seleccionada {s4.soloSeleccionado}  seleccionado {s4.Seleccionado}");
        if (id >= 0) registro.AppendLine(s4.DescribirElemento(id));
        registro.AppendLine();
    }

    /// La viga cuyo momento mas se curva por su propia carga: su diagrama es
    /// una parabola que se lee sola. Solo elige que mostrar.
    static int VigaConParabola(VisorSemana04 s4, string caso)
    {
        int mejor = -1;
        float mayor = 0f;
        foreach (ElementoS4 e in s4.Anexo.elementos)
        {
            if (e.tipo == null || !e.tipo.StartsWith("viga") || !e.cargada) continue;
            CasoS4 c = s4.Anexo.casos.Find(x => x.nombre == caso);
            if (c == null) return -1;
            EsfuerzosS4 s = c.esfuerzos.Find(x => x.id == e.id);
            if (s == null || s.My == null || s.My.Length < 3) continue;
            float medio = Mathf.Abs(s.My[s.My.Length / 2] - 0.5f * (s.My[0] + s.My[s.My.Length - 1]));
            if (medio > mayor) { mayor = medio; mejor = e.id; }
        }
        return mejor;
    }

    /// Centra la camara en los nodos del piso filtrado, para que sus
    /// diagramas se lean. Solo elige el encuadre.
    static void EncuadrarNivel(VisorQA qa, CamaraOrbital cam)
    {
        VisorEstructura v = FindAnyObjectByType<VisorEstructura>();
        if (v == null || v.Modelo == null || v.Modelo.nodos == null) { cam.EncuadrarTodo(); return; }
        bool hay = false;
        Bounds b = default;
        foreach (Nodo n in v.Modelo.nodos)
        {
            if (!qa.NivelVisible((float)n.z)) continue;
            Vector3 p = Ejes.PosicionDe(n);
            if (!hay) { b = new Bounds(p, Vector3.zero); hay = true; }
            else b.Encapsulate(p);
        }
        if (!hay) { cam.EncuadrarTodo(); return; }
        cam.centro = b.center;
        cam.distancia = Mathf.Clamp(b.extents.magnitude * 1.5f, 10f, 150f);
    }

    /// El momento del plano del muro, tal como lo trae el JSON.
    static string EnSuPlano(VisorSemana04 s4, int id)
    {
        ElementoS4 e = s4.ElementoPorId(id);
        return e != null && e.momento_en_el_plano == "My" ? "My" : "Mz";
    }

    /// Pide a VisorQA que rehaga sus capas en el proximo frame.
    static void Refrescar(VisorQA qa)
    {
        FieldInfo f = typeof(VisorQA).GetField("refrescar", BindingFlags.NonPublic | BindingFlags.Instance);
        if (f != null) f.SetValue(qa, true);
    }

    static void Scroll(VisorQA qa, float y)
    {
        FieldInfo f = typeof(VisorQA).GetField("scroll", BindingFlags.NonPublic | BindingFlags.Instance);
        if (f != null) f.SetValue(qa, new Vector2(0f, y));
    }

    static void Angulo(CamaraOrbital cam, float pitch, float yaw)
    {
        const BindingFlags B = BindingFlags.NonPublic | BindingFlags.Public | BindingFlags.Instance;
        FieldInfo fp = typeof(CamaraOrbital).GetField("pitch", B);
        FieldInfo fy = typeof(CamaraOrbital).GetField("yaw", B);
        if (fp != null) fp.SetValue(cam, pitch);
        if (fy != null) fy.SetValue(cam, yaw);
    }
}
