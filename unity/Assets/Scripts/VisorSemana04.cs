/*
================================================================
  VisorSemana04.cs
================================================================
  Unity como POSTPROCESADOR de los resultados de OpenSees. Lee
  StreamingAssets/semana04.json, que produce
  semana04/exportar_unity.py, y dibuja lo que ahi viene calculado:

    - los esfuerzos internos de cada barra en el CASO ACTIVO, como
      diagrama (My, Mz, Vz, Vy, N o T) sobre la geometria sin deformar;
    - la deformada del caso activo, sea un caso base o una combinacion;
    - la curva P-M de la seccion seleccionada con su punto de demanda;
    - el bloque de datos y de trazabilidad que VisorQA agrega a su
      panel al seleccionar un elemento.

  ----------------------------------------------------------------
  REGLA QUE NO SE ROMPE: aca no se calcula estructura
  ----------------------------------------------------------------
  Los esfuerzos a lo largo de la barra, las combinaciones, la curva
  P-M y la demanda vienen hechos de Python. Este script solo escala
  valores para que se vean, busca el mayor para ponerle etiqueta, y
  arma mallas y texto. Si aca se calculara algo habria dos
  implementaciones de la misma mecanica -- la de Python, verificada,
  y esta -- y tarde o temprano la pantalla mostraria algo distinto de
  lo que se comprobo.

  ----------------------------------------------------------------
  DE QUE LADO SE DIBUJA
  ----------------------------------------------------------------
  Del lado TRACCIONADO, que es la convencion de hormigon armado. Con
  los esfuerzos internos del contrato (cara positiva):

      My > 0 tracciona la fibra +z local  -> la curva va en +My * z_local
      Mz < 0 tracciona la fibra +y local  -> la curva va en -Mz * y_local

  Corte y axial no tienen lado traccionado: Vz, N y T van en z_local,
  Vy en y_local, y el color dice el signo. Los ejes locales son los
  del modelo base (Elemento.localY / localZ), que salen de la misma
  regla que usa el servidor. Ver semana04/CONTRATO.md.

  ----------------------------------------------------------------
  COMO SE USA
  ----------------------------------------------------------------
  Si la escena no lo trae, VisorQA lo agrega solo al arrancar, y sus
  controles van dentro del panel de VisorQA, seccion "Semana 4".
  Click en una barra -> el panel suma material, seccion,
  restricciones, esfuerzos del caso activo y trazabilidad; si la
  barra tiene fierro, se abre la ventana con su curva P-M.
================================================================
*/

using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using UnityEngine;


// ================================================================
// CONTRATO: las clases que JsonUtility llena desde semana04.json
// ----------------------------------------------------------------
// JsonUtility NO avisa cuando un nombre no calza: deja el campo en su
// valor por defecto y sigue. Cada nombre de aca tiene que ser la clave
// exacta del JSON. semana04/test_contrato_semana04.py lo comprueba en
// las dos direcciones y verificar_unity_semana04.py le hace leer el
// archivo a Unity de verdad. Un campo por linea, para que el test los
// pueda leer, y nada de metodos dentro de estas clases.
// ================================================================

[System.Serializable]
public class InfoSemana04
{
    public string edificio;
    public string descripcion;
    public string unidades;
    public string[] parametros;
    public string[] convencion;
    public string generado_por;
    public string caso_por_defecto;
    public int columna_demo;
    public int muro_demo;
    public int n_estaciones_cargada;
    public float cota_redondeo_kN;
}

/// Esfuerzos de UNA barra en un caso. f son los 12 de localForce,
/// fuerzas SOBRE la barra en ejes locales; x son las estaciones desde
/// el nodo i, y N..Mz los esfuerzos internos en cada estacion, ya
/// calculados en Python.
[System.Serializable]
public class EsfuerzosS4
{
    public int id;
    public float[] f;
    public float[] x;
    public float[] N;
    public float[] Vy;
    public float[] Vz;
    public float[] T;
    public float[] My;
    public float[] Mz;
}

[System.Serializable]
public class DemandaS4
{
    public int id;
    public int familia;
    public float P;
    public float M;
    public float M_fuera_plano;
    public string extremo;
    public float Mn;
    public float u;
    public bool pasa;
}

[System.Serializable]
public class CasoS4
{
    public string nombre;
    public string tipo;
    public string descripcion;
    public float[] factores;
    public float max_desplazamiento_mm;
    public List<DespNodo> desplazamientos;
    public List<EsfuerzosS4> esfuerzos;
    public List<DemandaS4> demandas;
}

[System.Serializable]
public class ElementoS4
{
    public int id;
    public int n1;
    public int n2;
    public string tipo;
    public string seccion;
    public string momento_en_el_plano;   // muro: "My" o "Mz"; si no, ""
    public float L;
    public string objeto_unity;
    public string tag_opensees;
    public string material;
    public float fpc_MPa;
    public float E_kPa;
    public float G_kPa;
    public float poisson;
    public float gamma;
    public float A;
    public float Iy;
    public float Iz;
    public float J;
    public float b;
    public float h;
    public float[] vecxz;
    public int[] restr_n1;
    public int[] restr_n2;
    public int diafragma_n1;
    public int diafragma_n2;
    public bool es_brazo_rigido;
    public string condiciones;
    public bool cargada;
    public int familia;
    public string resultados;
}

[System.Serializable]
public class FamiliaPM
{
    public int indice;
    public string clave;
    public string tipo;
    public string seccion;
    public float b;
    public float h;
    public float As_cm2;
    public float cuantia_pct;
    public string refuerzo;
    public string fuente;
    public float[] P;
    public float[] Mn;
    public float[] Mmax;
    public string[] de;
    public int[] elementos;
}

[System.Serializable]
public class AnexoSemana04
{
    public InfoSemana04 info;
    public List<CasoS4> casos;
    public List<ElementoS4> elementos;
    public List<FamiliaPM> familias;
}


// ================================================================
// EL VISOR
// ================================================================
public partial class VisorSemana04 : MonoBehaviour
{
    [Header("Archivo")]
    public string nombreArchivo = "semana04.json";

    [Header("Caso activo")]
    [Tooltip("Vacio = el caso por defecto del anexo. Manda sobre los " +
             "diagramas, los esfuerzos del panel, el punto de demanda " +
             "P-M y la deformada 'Caso activo (S4)'.")]
    public string casoActivo = "";

    [Header("Diagramas")]
    public bool mostrarDiagramas = true;

    [Tooltip("My, Mz, Vz, Vy, N o T.")]
    public string magnitud = "My";

    [Tooltip("true: solo la barra seleccionada. false: todas las que el " +
             "visor dibuja y pasan el filtro de piso de VisorQA.")]
    public bool soloSeleccionado = true;

    [Tooltip("El mayor |valor| de la magnitud entre las barras dibujadas " +
             "se dibuja con este largo, en metros. Es solo grafico: no " +
             "cambia ningun numero.")]
    public float largoDiagramaMaximo = 2f;

    [Range(0.1f, 5f)] public float multiplicadorEscala = 1f;

    public Color colorPositivo = new Color(0.25f, 0.55f, 1f);
    public Color colorNegativo = new Color(1f, 0.40f, 0.25f);
    public Color colorContorno = new Color(0.08f, 0.08f, 0.10f);
    public Color colorEtiqueta = new Color(0.05f, 0.05f, 0.05f);

    [Header("Curva P-M")]
    public bool mostrarPM = true;

    // --- lo que se lee ---
    public AnexoSemana04 Anexo { get; private set; }
    public int Seleccionado { get; private set; } = -1;

    /// Texto para el panel cuando algo impide usar el anexo.
    public string Aviso { get; private set; } = "";
    public bool AnexoCalzaConElModelo { get; private set; }

    /// Lo escucha VisorQA: si esta mostrando la deformada del caso
    /// activo la tiene que cambiar, y el texto del panel tambien.
    public event System.Action CambioCasoActivo;

    public static readonly string[] MAGNITUDES = { "My", "Mz", "Vz", "Vy", "N", "T" };

    // --- indices: se arman una vez al cargar ---
    private readonly Dictionary<int, ElementoS4> elementoPorId =
        new Dictionary<int, ElementoS4>();
    private readonly Dictionary<string, CasoS4> casoPorNombre =
        new Dictionary<string, CasoS4>();
    private readonly Dictionary<string, Dictionary<int, EsfuerzosS4>> esfuerzos =
        new Dictionary<string, Dictionary<int, EsfuerzosS4>>();
    private readonly Dictionary<string, Dictionary<int, DemandaS4>> demandas =
        new Dictionary<string, Dictionary<int, DemandaS4>>();

    // --- referencias ---
    private VisorEstructura visor;
    private VisorQA qa;
    private CamaraOrbital camara;

    // --- estado ---
    private readonly List<GameObject> creados = new List<GameObject>();
    private readonly Dictionary<Color, Material> materiales =
        new Dictionary<Color, Material>();
    private bool deformadaPuesta = false;
    private bool necesitaRedibujar = false;

    // ============================================================
    void Start()
    {
        visor = FindAnyObjectByType<VisorEstructura>();
        qa = FindAnyObjectByType<VisorQA>();
        camara = FindAnyObjectByType<CamaraOrbital>();
        if (Cargar()) StartCoroutine(PrepararCuandoElVisorEsteListo());
    }

    /// Se espera un frame: VisorEstructura carga su modelo en su Start()
    /// y el orden entre dos Start() no esta garantizado.
    IEnumerator PrepararCuandoElVisorEsteListo()
    {
        yield return null;
        ComprobarModelo();
        if (string.IsNullOrEmpty(casoActivo) || !casoPorNombre.ContainsKey(casoActivo))
            casoActivo = Anexo.info != null ? Anexo.info.caso_por_defecto : "";
        if (!casoPorNombre.ContainsKey(casoActivo ?? "") && Anexo.casos.Count > 0)
            casoActivo = Anexo.casos[0].nombre;
        Redibujar();
    }

    // Los campos del Inspector se aplican en caliente con el mismo
    // mecanismo que los otros visores: OnValidate no puede destruir
    // objetos, asi que solo levanta la bandera y Update redibuja.
    void OnValidate()
    {
        if (Application.isPlaying && Anexo != null) necesitaRedibujar = true;
    }

    void Update()
    {
        if (necesitaRedibujar) { necesitaRedibujar = false; Redibujar(); }
    }

    // ============================================================
    // CARGA
    // ============================================================
    bool Cargar()
    {
        string ruta = Path.Combine(Application.streamingAssetsPath, nombreArchivo);
        if (!File.Exists(ruta))
        {
            Aviso = "Falta " + nombreArchivo + " en StreamingAssets. Generalo con:\n"
                  + "  python semana04/exportar_unity.py <edificio>";
            Debug.LogError("VisorSemana04: no encontre " + ruta
                           + ". Corre primero: python semana04/exportar_unity.py <edificio>");
            return false;
        }
        try
        {
            Anexo = JsonUtility.FromJson<AnexoSemana04>(File.ReadAllText(ruta));
        }
        catch (System.Exception ex)
        {
            Anexo = null;
            Aviso = "No pude leer " + nombreArchivo + ": " + ex.Message;
            Debug.LogError("VisorSemana04: " + Aviso);
            return false;
        }
        if (Anexo == null || Anexo.casos == null || Anexo.elementos == null)
        {
            Anexo = null;
            Aviso = nombreArchivo + " no trae casos o elementos: vuelve a exportarlo.";
            Debug.LogError("VisorSemana04: " + Aviso);
            return false;
        }
        ConstruirIndices();
        return true;
    }

    void ConstruirIndices()
    {
        elementoPorId.Clear();
        casoPorNombre.Clear();
        esfuerzos.Clear();
        demandas.Clear();

        foreach (ElementoS4 e in Anexo.elementos) elementoPorId[e.id] = e;
        foreach (CasoS4 c in Anexo.casos)
        {
            casoPorNombre[c.nombre] = c;

            var porId = new Dictionary<int, EsfuerzosS4>();
            if (c.esfuerzos != null)
                foreach (EsfuerzosS4 s in c.esfuerzos) porId[s.id] = s;
            esfuerzos[c.nombre] = porId;

            var dem = new Dictionary<int, DemandaS4>();
            if (c.demandas != null)
                foreach (DemandaS4 d in c.demandas) dem[d.id] = d;
            demandas[c.nombre] = dem;
        }
    }

    /// El anexo tiene que ser del MISMO modelo que dibuja el visor. Si se
    /// exporto otro edificio, los ids existen igual pero son otras barras:
    /// el panel mostraria los esfuerzos de una barra sobre otra, sin error.
    void ComprobarModelo()
    {
        AnexoCalzaConElModelo = false;
        if (visor == null || visor.Modelo == null || visor.Modelo.elementos == null)
        {
            Aviso = "No hay un VisorEstructura con modelo cargado.";
            return;
        }

        var delModelo = new Dictionary<int, Elemento>();
        foreach (Elemento e in visor.Modelo.elementos) delModelo[e.id] = e;

        int distintos = 0;
        foreach (ElementoS4 a in Anexo.elementos)
        {
            Elemento m;
            if (!delModelo.TryGetValue(a.id, out m) || m.n1 != a.n1
                || m.n2 != a.n2 || m.seccion != a.seccion)
                distintos++;
        }

        AnexoCalzaConElModelo = delModelo.Count == Anexo.elementos.Count && distintos == 0;
        if (AnexoCalzaConElModelo)
        {
            Aviso = "";
            return;
        }
        string ed = Anexo.info != null ? Anexo.info.edificio : "?";
        Aviso = $"El anexo es de otro modelo: '{ed}', {Anexo.elementos.Count} elementos; "
              + $"el visor tiene {delModelo.Count} y {distintos} no calzan.\n"
              + "Exporta el edificio que muestra el visor:\n"
              + "  python semana04/exportar_unity.py <edificio>";
        Debug.LogWarning("VisorSemana04: " + Aviso);
    }

    // ============================================================
    // API QUE USA VisorQA
    // ============================================================
    public CasoS4 CasoActivo()
    {
        CasoS4 c;
        return (Anexo != null && casoPorNombre.TryGetValue(casoActivo ?? "", out c)) ? c : null;
    }

    public ElementoS4 ElementoPorId(int id)
    {
        ElementoS4 e;
        return elementoPorId.TryGetValue(id, out e) ? e : null;
    }

    /// Esfuerzos de la barra en el caso activo, o null.
    public EsfuerzosS4 EsfuerzosDe(int id)
    {
        Dictionary<int, EsfuerzosS4> porId;
        EsfuerzosS4 s;
        return (esfuerzos.TryGetValue(casoActivo ?? "", out porId)
                && porId.TryGetValue(id, out s)) ? s : null;
    }

    public DemandaS4 DemandaDe(int id, string caso)
    {
        Dictionary<int, DemandaS4> dem;
        DemandaS4 d;
        return (demandas.TryGetValue(caso ?? "", out dem)
                && dem.TryGetValue(id, out d)) ? d : null;
    }

    public void ElegirCaso(string nombre)
    {
        if (Anexo == null || nombre == casoActivo || !casoPorNombre.ContainsKey(nombre))
            return;
        casoActivo = nombre;
        texturaPMFirma = null;
        if (deformadaPuesta) AplicarDeformadaDelCaso();
        Redibujar();
        if (CambioCasoActivo != null) CambioCasoActivo();
    }

    /// Lo llama VisorQA al seleccionar una barra, y los botones de demo.
    public void Seleccionar(int id)
    {
        Seleccionado = id;
        texturaPMFirma = null;
        Redibujar();
    }

    /// La deformada del caso activo, con los desplazamientos del anexo.
    /// VisorQA la pide con el modo "Caso activo (S4)".
    public void AplicarDeformadaDelCaso()
    {
        CasoS4 c = CasoActivo();
        if (visor == null || c == null || c.desplazamientos == null) return;
        visor.mostrarDeformada = true;
        visor.AplicarDeformada(c.desplazamientos);      // ya redibuja
        deformadaPuesta = true;
    }

    /// Solo quita la deformada si la puso ESTE script. La de gravedad y la
    /// de sismo las ponen otros, y borrarlas aca las apagaria en el mismo
    /// frame en que se eligen: el mismo cuidado que VisorSemana03.
    public void QuitarDeformada()
    {
        if (!deformadaPuesta || visor == null) return;
        deformadaPuesta = false;
        visor.LimpiarDeformada();
        visor.Redibujar();
    }

    public bool MouseSobreVentana(Vector2 posGUI)
    {
        return VentanaPMVisible() && ventanaPM.Contains(posGUI);
    }

    /// Centra la camara orbital en la barra: sirve en la demo para no
    /// buscar la columna a mano en un edificio de 50 m.
    public void EnfocarElemento(int id)
    {
        if (camara == null || visor == null || visor.Modelo == null) return;
        Elemento e = null;
        foreach (Elemento x in visor.Modelo.elementos)
            if (x.id == id) { e = x; break; }
        if (e == null) return;

        Nodo a = visor.Modelo.NodoPorId(e.n1);
        Nodo b = visor.Modelo.NodoPorId(e.n2);
        if (a == null || b == null) return;

        Vector3 pa = Ejes.PosicionDe(a), pb = Ejes.PosicionDe(b);
        camara.centro = (pa + pb) * 0.5f;
        ElementoS4 s = ElementoPorId(id);
        float tam = Mathf.Max(Vector3.Distance(pa, pb),
                              s != null ? Mathf.Max(s.b, s.h) : 0f);
        camara.distancia = Mathf.Clamp(tam * 3.5f, 8f, 80f);
    }

    // Sigue en VisorSemana04.Diagramas.cs, .PM.cs y .Panel.cs.
}
