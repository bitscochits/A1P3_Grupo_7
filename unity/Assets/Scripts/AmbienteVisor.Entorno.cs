/*
================================================================
  AmbienteVisor.Entorno.cs
================================================================
  Lo que rodea a la estructura en la vista realista: VENTANAS entre
  pisos, AUTOS estacionados y ARBOLES. Solo DIBUJO: ningun calculo los
  ve, no tienen collider y no estan en ObjetosDeElementos (ni el mapa
  D/C ni la seleccion los tocan).

  ----------------------------------------------------------------
  DE DONDE SALE (nada deducido aca)
  ----------------------------------------------------------------
  StreamingAssets/entorno.json, que arma Python:
      edificios/conjunto/entorno.py  ->  data/unity/entorno_<ed>.json
      comun/lanzar_unity.py sincronizar <ed>  ->  StreamingAssets/entorno.json
  y las mallas de autos y arboles, Resources/Entorno/modelos.json (el
  mismo script, de los OBJ de Kenney, CC0). Python decide cada vano (de
  las vigas de fachada, los pilares y los muros del modelo) y cada auto y
  arbol (de OpenStreetMap, sobre la misma malla del relieve). Aca solo se
  arman las mallas. Supuestos: edificios/conjunto/sitio/entorno.json.

  ----------------------------------------------------------------
  REGLAS
  ----------------------------------------------------------------
  - VENTANAS: un GameObject por vano (antepecho y marco, con sombra) y un
    hijo con el vidrio (sin sombra: en URP un transparente la proyecta).
    Se ven con la MISMA regla que las losas (PiezasDeDibujoALaVista,
    AmbienteVisor.Losas.cs): no siguen a la deformada, asi que se
    esconden con ella, con la carga movil, los diagramas y el mapa D/C.
    Respetan el filtro de piso (la cota de su losa) y abren el pozo de
    la seleccion como las losas.
  - El VIDRIO es una copia de Resources/Ambiente/Mat_vidrio (transparente,
    armado por Editor/RecursosRealistas.cs: un 'new Material'
    transparente sale opaco en el exe). Sin ese asset, vidrio opaco
    oscuro. Dos caras (adelante y atras), cada una con su normal.
  - AUTOS y ARBOLES: estan quietos, asi que se juntan en UNA malla por
    material (CombineMeshes): unos 20 renderers en vez de mil, que el
    telefono agradece. Van sobre el relieve: si el relieve no esta a la
    vista, no se ven (flotarian sobre el plano del suelo).
  - Si falta el archivo o es de otro modelo, no se dibuja nada y el
    panel lo dice (AjustesVista.entornoEstado), como el relieve.
================================================================
*/

using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using UnityEngine;
using UnityEngine.Rendering;

[Serializable]
public class EntornoJson
{
    public InfoEntorno info;
    public VentanaFachada[] ventanas;
    public ObjetoSitio[] objetos;
    public PavimentoEntorno[] pavimentos;
}

[Serializable]
public class InfoEntorno
{
    public string edificio, generado_por, fuente_sitio, modelos, _por_que;
    public int n_nodos, n_elementos;    // la huella del modelo del visor
    public int n_ventanas, n_autos, n_arboles;
    public float marco_m, profundidad_marco_m, espesor_antepecho_m, area_vidrio_m2;
}

/// Un vano con ventana. (x, y, z): la esquina de abajo en el plano del
/// vidrio; u: a lo largo de la fachada; n: hacia afuera. OpenSees, m.
[Serializable]
public class VentanaFachada
{
    public float piso, x, y, z, ux, uy, nx, ny, ancho, alto, antepecho;
    public int divisiones;
}

/// Un auto o un arbol. frente y arriba en ejes OpenSees; escala 1 en los
/// autos (la malla ya esta en metros) y la altura en los arboles.
[Serializable]
public class ObjetoSitio
{
    public string tipo, modelo;
    public float x, y, z, escala;
    public float[] frente, arriba, color;
}

/// El piso de un material (asfalto, vereda, linea): triangulos ya pegados al
/// relieve por Python, x, y, z (OpenSees) de a tres por triangulo.
[Serializable]
public class PavimentoEntorno
{
    public string material;
    public float[] vertices;
}

[Serializable]
public class ModelosEntornoJson
{
    public InfoModelosEntorno info;
    public MaterialEntorno[] materiales;
    public ModeloEntorno[] modelos;
}

[Serializable]
public class InfoModelosEntorno
{
    public string fuente, generado_por, _por_que;
}

[Serializable]
public class MaterialEntorno
{
    public string nombre;
    public float[] color;               // sRGB (+ alfa)
    public float suavidad, metalico;
    public bool por_objeto;             // el color lo pone cada objeto
}

[Serializable]
public class ModeloEntorno
{
    public string nombre, tipo;
    public float largo_m, ancho_m, alto_m;
    public ParteModelo[] partes;
}

[Serializable]
public class ParteModelo
{
    public string material;
    public float[] vertices;            // de a tres por triangulo, ejes de Unity
}

public partial class AmbienteVisor
{
    const string ARCHIVO_ENTORNO = "entorno.json";
    const string RECURSO_MODELOS_ENTORNO = "Entorno/modelos";

    private EntornoJson entorno;
    private int pedidoEntorno;            // sube en cada modelo cargado
    private GameObject raizEntorno;
    private readonly List<GameObject> ventanasGO = new List<GameObject>();
    private readonly List<VentanaFachada> ventanasDato = new List<VentanaFachada>();
    private readonly List<Rect> plantaVentanas = new List<Rect>();
    private GameObject sitioGO;
    private readonly List<Mesh> mallasEntorno = new List<Mesh>();
    private ModelosEntornoJson modelosEntorno;
    private bool modelosEntornoLeidos;
    private readonly Dictionary<string, Mesh[]> mallasDeModelo = new Dictionary<string, Mesh[]>();
    private readonly Dictionary<string, Material> materialesEntorno = new Dictionary<string, Material>();
    private string firmaVisibilidadEntorno;

    // ============================================================
    // CARGA
    // ============================================================
    /// Lo llama AlCargarModelo: un modelo NUEVO, se vuelve a leer el archivo.
    void PedirEntornoDelModelo()
    {
        pedidoEntorno++;
        entorno = null;
        BorrarEntorno();
        AjustesVista.entornoEstado = "Buscando ventanas, autos y arboles...";
        StartCoroutine(PedirEntorno(pedidoEntorno, visor.Modelo.nodos.Count, visor.Modelo.elementos.Count));
    }

    IEnumerator PedirEntorno(int pedido, int nNodos, int nElementos)
    {
        string texto = null, error = null;
        yield return LectorStreaming.Leer(ARCHIVO_ENTORNO, t => texto = t, e => error = e);
        if (pedido != pedidoEntorno) yield break;     // ya se cargo otro modelo

        if (error != null)
        {
            AjustesVista.entornoEstado = "Sin ventanas, autos ni arboles: no hay StreamingAssets/entorno.json "
                + "(lo arma edificios/conjunto/entorno.py y lo copia lanzar_unity.py sincronizar).";
            Debug.Log("AmbienteVisor: " + AjustesVista.entornoEstado);
            yield break;
        }
        EntornoJson t = null;
        try { t = JsonUtility.FromJson<EntornoJson>(texto); }
        catch (Exception ex) { Debug.LogException(ex); }
        string problema = null;
        if (t == null || t.info == null) problema = "no se pudo leer entorno.json";
        else if (t.info.n_nodos != nNodos || t.info.n_elementos != nElementos)
            problema = string.Format("entorno.json es de '{0}' ({1} nodos, {2} elementos) y el modelo cargado "
                + "tiene {3} nodos y {4} elementos: se copia con lanzar_unity.py sincronizar <edificio>",
                t.info.edificio, t.info.n_nodos, t.info.n_elementos, nNodos, nElementos);
        if (problema != null)
        {
            AjustesVista.entornoEstado = "Sin ventanas, autos ni arboles: " + problema + ".";
            Debug.LogWarning("AmbienteVisor: " + AjustesVista.entornoEstado);
            yield break;
        }
        entorno = t;
        AjustesVista.entornoEstado = string.Format(CultureInfo.InvariantCulture,
            "{0} vanos con ventana ({1:F0} m2 de vidrio) en las fachadas del modelo ({2}); {3} autos y {4} "
            + "arboles donde OpenStreetMap pone estacionamientos, calles y areas verdes. Modelos de Kenney (CC0); "
            + "{5}. Solo dibujo.",
            t.info.n_ventanas, t.info.area_vidrio_m2, t.info.edificio, t.info.n_autos, t.info.n_arboles,
            t.info.fuente_sitio);
        if (visor != null && visor.Modelo != null) ConstruirEntorno();
    }

    /// Lo llama ActualizarSueloSinCortar en cada carga y redibujado: depende
    /// solo de los JSON, asi que se arma una vez por modelo.
    void ActualizarEntorno()
    {
        if (entorno != null && raizEntorno == null) ConstruirEntorno();
    }

    void ConstruirEntorno()
    {
        BorrarEntorno();
        raizEntorno = new GameObject("Entorno");
        raizEntorno.transform.SetParent(transform, false);
        System.Diagnostics.Stopwatch reloj = System.Diagnostics.Stopwatch.StartNew();
        ConstruirVentanas();
        int nObjetos = ConstruirSitio();
        firmaVisibilidadEntorno = null;
        ActualizarVisibilidadEntorno();
        Debug.Log(string.Format(CultureInfo.InvariantCulture,
            "AmbienteVisor: entorno de '{0}': {1} ventanas, {2} autos y arboles en {3} mallas, en {4} ms.",
            entorno.info.edificio, ventanasGO.Count, nObjetos, mallasEntorno.Count, reloj.ElapsedMilliseconds));
    }

    void BorrarEntorno()
    {
        if (raizEntorno != null) Destroy(raizEntorno);
        raizEntorno = null;
        sitioGO = null;
        foreach (Mesh m in mallasEntorno) if (m != null) Destroy(m);
        mallasEntorno.Clear();
        ventanasGO.Clear();
        ventanasDato.Clear();
        plantaVentanas.Clear();
        firmaVisibilidadEntorno = null;
    }

    // ============================================================
    // CUANDO SE VEN
    // ============================================================
    /// Lo llama Update en cada cuadro: solo toca algo si cambio.
    void ActualizarVisibilidadEntorno()
    {
        if (raizEntorno == null) return;
        bool ventanas = ventanasGO.Count > 0 && AjustesVista.ventanas && PiezasDeDibujoALaVista();
        float zSel = float.PositiveInfinity;
        Vector2 selA = Vector2.zero, selB = Vector2.zero;
        bool haySel = ventanas && Seleccion(visor.Modelo, out zSel, out selA, out selB);
        bool sitio = sitioGO != null && AjustesVista.realista && AjustesVista.entorno
                     && relieve != null && relieve.activeSelf;

        var sb = new System.Text.StringBuilder(ventanasGO.Count + 1);
        sb.Append(sitio ? '1' : '0');
        for (int i = 0; i < ventanasGO.Count; i++)
        {
            VentanaFachada v = ventanasDato[i];
            bool ver = ventanas && AjustesVista.EnCotaVisible(v.piso);
            // El pozo de la seleccion, como las losas: lo de ese piso y de
            // arriba que esta cerca en planta.
            if (ver && haySel && v.z + v.alto > zSel + AjustesVista.TOLERANCIA_COTA
                && DistanciaARect(plantaVentanas[i], selA, selB) < MARGEN_POZO)
                ver = false;
            sb.Append(ver ? '1' : '0');
        }
        string firma = sb.ToString();
        if (firma == firmaVisibilidadEntorno) return;
        firmaVisibilidadEntorno = firma;
        if (sitioGO != null && sitioGO.activeSelf != sitio) sitioGO.SetActive(sitio);
        for (int i = 0; i < ventanasGO.Count; i++)
        {
            bool ver = firma[i + 1] == '1';
            if (ventanasGO[i] != null && ventanasGO[i].activeSelf != ver) ventanasGO[i].SetActive(ver);
        }
    }

    // ============================================================
    // LAS VENTANAS
    // ============================================================
    void ConstruirVentanas()
    {
        if (entorno.ventanas == null || entorno.ventanas.Length == 0) return;
        Transform raiz = new GameObject("Ventanas").transform;
        raiz.SetParent(raizEntorno.transform, false);
        Material[] mats = { MaterialAntepecho(), MatEntorno("marco") };
        Material vidrio = MaterialVidrio();
        InfoEntorno inf = entorno.info;
        foreach (VentanaFachada v in entorno.ventanas)
        {
            Mesh caja, cristal;
            MallasDeVentana(v, inf.marco_m, inf.profundidad_marco_m, inf.espesor_antepecho_m, out caja, out cristal);
            var go = new GameObject("Ventana_z" + v.piso.ToString("0.00", CultureInfo.InvariantCulture));
            go.transform.SetParent(raiz, false);
            go.AddComponent<MeshFilter>().sharedMesh = caja;
            MeshRenderer mr = go.AddComponent<MeshRenderer>();
            mr.sharedMaterials = mats;
            mr.shadowCastingMode = ShadowCastingMode.On;
            mr.receiveShadows = true;
            var gv = new GameObject("Vidrio");
            gv.transform.SetParent(go.transform, false);
            gv.AddComponent<MeshFilter>().sharedMesh = cristal;
            MeshRenderer mv = gv.AddComponent<MeshRenderer>();
            mv.sharedMaterial = vidrio;
            mv.shadowCastingMode = ShadowCastingMode.Off;
            mv.receiveShadows = true;
            // Sin Collider a proposito (ver el encabezado).
            ventanasGO.Add(go);
            ventanasDato.Add(v);
            float x2 = v.x + v.ux * v.ancho, y2 = v.y + v.uy * v.ancho;
            plantaVentanas.Add(Rect.MinMaxRect(Mathf.Min(v.x, x2), Mathf.Min(v.y, y2),
                                               Mathf.Max(v.x, x2), Mathf.Max(v.y, y2)));
            mallasEntorno.Add(caja);
            mallasEntorno.Add(cristal);
        }
    }

    /// El antepecho y el marco (submallas 0 y 1) y el vidrio, en el mundo.
    /// Coordenadas del vano: s a lo largo (0..ancho), h hacia arriba desde
    /// la losa (0..alto), d hacia afuera desde el plano del vidrio.
    static void MallasDeVentana(VentanaFachada v, float marco, float prof, float espAntepecho,
                                out Mesh caja, out Mesh cristal)
    {
        Func<float, float, float, Vector3> P = (s, h, d) =>
            Ejes.AUnity(v.x + v.ux * s + v.nx * d, v.y + v.uy * s + v.ny * d, v.z + h);
        Vector3 afuera = Ejes.AUnity(v.nx, v.ny, 0f).normalized;
        Vector3 aLoLargo = Ejes.AUnity(v.ux, v.uy, 0f).normalized;

        var vs = new List<Vector3>();
        var ns = new List<Vector3>();
        var uv = new List<Vector2>();
        var triAntepecho = new List<int>();
        var triMarco = new List<int>();
        float w = v.ancho, H = v.alto, a = v.antepecho, m = marco;

        if (a > 0.01f)
            Caja(vs, ns, uv, triAntepecho, P, aLoLargo, afuera, 0f, w, 0f, a, -0.5f * espAntepecho, 0.5f * espAntepecho);
        // Los travesanos van de punta a punta y los montantes ENTRE ellos, un
        // poco menos profundos: ninguna cara queda en el mismo plano que otra.
        float d1 = 0.5f * prof, d2 = 0.45f * prof, d3 = 0.40f * prof;
        Caja(vs, ns, uv, triMarco, P, aLoLargo, afuera, 0f, w, a, a + m, -d1, d1);              // alfeizar
        Caja(vs, ns, uv, triMarco, P, aLoLargo, afuera, 0f, w, H - m, H, -d1, d1);              // dintel
        Caja(vs, ns, uv, triMarco, P, aLoLargo, afuera, 0f, m, a + m, H - m, -d2, d2);          // jambas
        Caja(vs, ns, uv, triMarco, P, aLoLargo, afuera, w - m, w, a + m, H - m, -d2, d2);
        int k = Mathf.Max(1, v.divisiones);
        for (int j = 1; j < k; j++)
        {
            float sc = j * w / k;
            Caja(vs, ns, uv, triMarco, P, aLoLargo, afuera, sc - 0.5f * m, sc + 0.5f * m, a + m, H - m, -d2, d2);
        }
        // Un travesano alto: la banda de ventilacion de arriba.
        float ht = H - m - Mathf.Min(0.6f, 0.25f * (H - a));
        if (ht > a + 4f * m)
            for (int j = 0; j < k; j++)
            {
                float s0 = j == 0 ? m : j * w / k + 0.5f * m, s1 = j == k - 1 ? w - m : (j + 1) * w / k - 0.5f * m;
                Caja(vs, ns, uv, triMarco, P, aLoLargo, afuera, s0, s1, ht - 0.5f * m, ht + 0.5f * m, -d3, d3);
            }

        caja = new Mesh { name = "Ventana" };
        caja.SetVertices(vs);
        caja.SetNormals(ns);
        caja.SetUVs(0, uv);
        caja.subMeshCount = 2;
        caja.SetTriangles(triAntepecho, 0);
        caja.SetTriangles(triMarco, 1);
        caja.RecalculateTangents();          // para el mapa normal del hormigon del antepecho
        caja.RecalculateBounds();

        // El vidrio: dos caras, cada una con su normal (el material es de una).
        var cv = new List<Vector3>();
        var cn = new List<Vector3>();
        var cu = new List<Vector2>();
        var ct = new List<int>();
        Cara(cv, cn, cu, ct, P(m, a + m, 0f), P(w - m, a + m, 0f), P(w - m, H - m, 0f), P(m, H - m, 0f), afuera);
        Cara(cv, cn, cu, ct, P(m, a + m, 0f), P(w - m, a + m, 0f), P(w - m, H - m, 0f), P(m, H - m, 0f), -afuera);
        cristal = new Mesh { name = "Vidrio" };
        cristal.SetVertices(cv);
        cristal.SetNormals(cn);
        cristal.SetUVs(0, cu);
        cristal.SetTriangles(ct, 0);
        cristal.RecalculateBounds();
    }

    /// Una caja alineada con el vano: s0..s1 a lo largo, h0..h1 en altura,
    /// d0..d1 hacia afuera. Seis caras con normales propias; UV en metros /
    /// REPETICION_HORMIGON (el antepecho lleva la textura del hormigon).
    static void Caja(List<Vector3> vs, List<Vector3> ns, List<Vector2> uv, List<int> tri,
                     Func<float, float, float, Vector3> P, Vector3 aLoLargo, Vector3 afuera,
                     float s0, float s1, float h0, float h1, float d0, float d1)
    {
        if (s1 - s0 < 1e-4f || h1 - h0 < 1e-4f || d1 - d0 < 1e-4f) return;
        Cara(vs, ns, uv, tri, P(s0, h0, d1), P(s1, h0, d1), P(s1, h1, d1), P(s0, h1, d1), afuera);
        Cara(vs, ns, uv, tri, P(s0, h0, d0), P(s1, h0, d0), P(s1, h1, d0), P(s0, h1, d0), -afuera);
        Cara(vs, ns, uv, tri, P(s0, h1, d0), P(s1, h1, d0), P(s1, h1, d1), P(s0, h1, d1), Vector3.up);
        Cara(vs, ns, uv, tri, P(s0, h0, d0), P(s1, h0, d0), P(s1, h0, d1), P(s0, h0, d1), Vector3.down);
        Cara(vs, ns, uv, tri, P(s1, h0, d0), P(s1, h0, d1), P(s1, h1, d1), P(s1, h1, d0), aLoLargo);
        Cara(vs, ns, uv, tri, P(s0, h0, d0), P(s0, h0, d1), P(s0, h1, d1), P(s0, h1, d0), -aLoLargo);
    }

    /// Un cuadrilatero p0-p1-p2-p3 mirando hacia 'normal' (Unity toma como
    /// frente el lado de Cross(b - a, c - a)).
    static void Cara(List<Vector3> vs, List<Vector3> ns, List<Vector2> uv, List<int> tri,
                     Vector3 p0, Vector3 p1, Vector3 p2, Vector3 p3, Vector3 normal)
    {
        int b = vs.Count;
        vs.Add(p0); vs.Add(p1); vs.Add(p2); vs.Add(p3);
        bool vertical = Mathf.Abs(normal.y) < 0.5f;
        foreach (Vector3 p in new[] { p0, p1, p2, p3 })
        {
            ns.Add(normal);
            uv.Add(vertical ? new Vector2((p.x + p.z) / REPETICION_HORMIGON, p.y / REPETICION_HORMIGON)
                            : new Vector2(p.x / REPETICION_HORMIGON, p.z / REPETICION_HORMIGON));
        }
        if (Vector3.Dot(Vector3.Cross(p1 - p0, p2 - p0), normal) > 0f)
        { tri.Add(b); tri.Add(b + 1); tri.Add(b + 2); tri.Add(b); tri.Add(b + 2); tri.Add(b + 3); }
        else
        { tri.Add(b); tri.Add(b + 2); tri.Add(b + 1); tri.Add(b); tri.Add(b + 3); tri.Add(b + 2); }
    }

    // ============================================================
    // LOS AUTOS Y LOS ARBOLES
    // ============================================================
    /// Junta todos los objetos en una malla por material. Devuelve cuantos
    /// objetos dibujo.
    int ConstruirSitio()
    {
        if (entorno.objetos == null || entorno.objetos.Length == 0 || !CargarModelosEntorno()) return 0;
        var porMaterial = new Dictionary<string, List<CombineInstance>>();
        var materialDe = new Dictionary<string, Material>();
        int n = 0, sinModelo = 0;
        foreach (ObjetoSitio o in entorno.objetos)
        {
            Mesh[] mallas;
            ModeloEntorno mod = ModeloPorNombre(o.modelo);
            if (mod == null || !mallasDeModelo.TryGetValue(o.modelo, out mallas)) { sinModelo++; continue; }
            Vector3 frente = Ejes.AUnity(o.frente[0], o.frente[1], o.frente[2]);
            Vector3 arriba = Ejes.AUnity(o.arriba[0], o.arriba[1], o.arriba[2]);
            Matrix4x4 trs = Matrix4x4.TRS(Ejes.AUnity(o.x, o.y, o.z), Quaternion.LookRotation(frente, arriba),
                                          Vector3.one * o.escala);
            for (int k = 0; k < mod.partes.Length; k++)
            {
                MaterialEntorno me = MaterialDelModelo(mod.partes[k].material);
                string clave = mod.partes[k].material;
                if (me != null && me.por_objeto && o.color != null && o.color.Length >= 3)
                    clave += string.Format(CultureInfo.InvariantCulture, "_{0:F3}_{1:F3}_{2:F3}",
                                           o.color[0], o.color[1], o.color[2]);
                List<CombineInstance> lista;
                if (!porMaterial.TryGetValue(clave, out lista))
                {
                    porMaterial[clave] = lista = new List<CombineInstance>();
                    materialDe[clave] = me != null && me.por_objeto ? MatEntorno(me.nombre, o.color)
                                                                     : MatEntorno(mod.partes[k].material);
                }
                lista.Add(new CombineInstance { mesh = mallas[k], transform = trs });
            }
            n++;
        }
        if (sinModelo > 0)
            Debug.LogWarning("AmbienteVisor: " + sinModelo + " objetos del entorno con un modelo que no esta en "
                             + "Resources/Entorno/modelos.json (correr edificios/conjunto/entorno.py).");
        sitioGO = new GameObject("Autos y arboles");
        sitioGO.transform.SetParent(raizEntorno.transform, false);
        ConstruirPisos();
        foreach (KeyValuePair<string, List<CombineInstance>> kv in porMaterial)
        {
            var malla = new Mesh { name = "Entorno_" + kv.Key, indexFormat = IndexFormat.UInt32 };
            malla.CombineMeshes(kv.Value.ToArray(), true, true);
            malla.RecalculateBounds();
            mallasEntorno.Add(malla);
            var go = new GameObject(kv.Key);
            go.transform.SetParent(sitioGO.transform, false);
            go.AddComponent<MeshFilter>().sharedMesh = malla;
            MeshRenderer mr = go.AddComponent<MeshRenderer>();
            mr.sharedMaterial = materialDe[kv.Key];
            mr.shadowCastingMode = ShadowCastingMode.On;
            mr.receiveShadows = true;
        }
        return n;
    }

    /// El asfalto, las veredas y las lineas de los estacionamientos: una malla
    /// por material, hija de los autos (se ven con ellos y con el relieve).
    void ConstruirPisos()
    {
        if (entorno.pavimentos == null) return;
        foreach (PavimentoEntorno pv in entorno.pavimentos)
        {
            if (pv == null || pv.vertices == null || pv.vertices.Length < 9) continue;
            int nv = pv.vertices.Length / 3;
            var vs = new Vector3[nv];
            var uv = new Vector2[nv];
            for (int i = 0; i < nv; i++)
            {
                vs[i] = Ejes.AUnity(pv.vertices[3 * i], pv.vertices[3 * i + 1], pv.vertices[3 * i + 2]);
                uv[i] = new Vector2(vs[i].x / REPETICION_HORMIGON, vs[i].z / REPETICION_HORMIGON);
            }
            // Cada triangulo con la cara hacia arriba (el orden de Python es en
            // planta OpenSees; el cambio de ejes lo da vuelta).
            var ts = new int[nv - nv % 3];
            for (int i = 0; i + 2 < nv; i += 3)
            {
                bool arriba = Vector3.Cross(vs[i + 1] - vs[i], vs[i + 2] - vs[i]).y > 0f;
                ts[i] = i; ts[i + 1] = arriba ? i + 1 : i + 2; ts[i + 2] = arriba ? i + 2 : i + 1;
            }
            var malla = new Mesh { name = "Piso_" + pv.material, indexFormat = IndexFormat.UInt32 };
            malla.vertices = vs;
            malla.uv = uv;
            malla.triangles = ts;
            malla.RecalculateNormals();
            malla.RecalculateTangents();
            malla.RecalculateBounds();
            mallasEntorno.Add(malla);
            var go = new GameObject("Piso_" + pv.material);
            go.transform.SetParent(sitioGO.transform, false);
            go.AddComponent<MeshFilter>().sharedMesh = malla;
            MeshRenderer mr = go.AddComponent<MeshRenderer>();
            mr.sharedMaterial = pv.material == "linea" ? MatEntorno("linea") : MaterialPiso(pv.material);
            mr.shadowCastingMode = ShadowCastingMode.Off;
            mr.receiveShadows = true;
        }
    }

    /// Asfalto y vereda: la textura del hormigon de losa (si esta) con el
    /// color de la paleta, sin la mezcla de tinte de NuevoMaterialReal (que no
    /// deja oscurecer). Sin el recurso, el color liso.
    Material MaterialPiso(string nombre)
    {
        Material m;
        if (materialesEntorno.TryGetValue("piso_" + nombre, out m) && m != null) return m;
        Material b = BaseReal("hormigon_losa");
        if (b == null) return MatEntorno(nombre);
        MaterialEntorno me = MaterialDelModelo(nombre);
        Color c = me != null && me.color != null && me.color.Length >= 3
            ? new Color(me.color[0], me.color[1], me.color[2]) : Color.gray;
        m = new Material(b) { name = "Entorno_" + nombre, color = c };
        if (m.HasProperty("_BaseMap")) m.SetTextureScale("_BaseMap", Vector2.one * (REPETICION_HORMIGON / TILE_LOSA_M));
        FijarSiExiste(m, "_BaseColor", c);
        FijarSiExiste(m, "_Smoothness", me != null ? me.suavidad : 0.1f);
        misMateriales.Add(m);
        materialesEntorno["piso_" + nombre] = m;
        return m;
    }

    /// Lee Resources/Entorno/modelos.json y arma una malla por parte, una vez.
    bool CargarModelosEntorno()
    {
        if (modelosEntornoLeidos) return modelosEntorno != null;
        modelosEntornoLeidos = true;
        TextAsset t = Resources.Load<TextAsset>(RECURSO_MODELOS_ENTORNO);
        if (t == null)
        {
            Debug.LogWarning("AmbienteVisor: falta Resources/Entorno/modelos.json (edificios/conjunto/entorno.py).");
            return false;
        }
        ModelosEntornoJson j;
        try { j = JsonUtility.FromJson<ModelosEntornoJson>(t.text); }
        catch (Exception ex) { Debug.LogException(ex); return false; }
        if (j == null || j.modelos == null) return false;
        foreach (ModeloEntorno mod in j.modelos)
        {
            var mallas = new Mesh[mod.partes.Length];
            for (int k = 0; k < mod.partes.Length; k++)
            {
                float[] v = mod.partes[k].vertices;
                int nv = v.Length / 3;
                var vs = new Vector3[nv];
                var ts = new int[nv];
                for (int i = 0; i < nv; i++)
                {
                    vs[i] = new Vector3(v[3 * i], v[3 * i + 1], v[3 * i + 2]);
                    ts[i] = i;
                }
                // Las HOJAS se sueldan (vertices iguales, uno solo): normales
                // suaves, una copa redonda en vez de facetada. Lo demas queda
                // con caras planas, el estilo del modelo.
                if (mod.partes[k].material == "hojas") Soldar(ref vs, ts);
                var m = new Mesh { name = mod.nombre + "_" + mod.partes[k].material };
                if (vs.Length > 65000) m.indexFormat = IndexFormat.UInt32;
                m.vertices = vs;
                m.triangles = ts;
                m.RecalculateNormals();
                m.RecalculateBounds();
                mallas[k] = m;
            }
            mallasDeModelo[mod.nombre] = mallas;
        }
        modelosEntorno = j;
        return true;
    }

    /// Junta los vertices que estan en el mismo lugar (al decimo de mm) y
    /// renumera los triangulos.
    static void Soldar(ref Vector3[] vs, int[] ts)
    {
        var indice = new Dictionary<Vector3Int, int>();
        var nuevos = new List<Vector3>();
        var mapa = new int[vs.Length];
        for (int i = 0; i < vs.Length; i++)
        {
            var clave = new Vector3Int(Mathf.RoundToInt(vs[i].x * 1e4f), Mathf.RoundToInt(vs[i].y * 1e4f),
                                       Mathf.RoundToInt(vs[i].z * 1e4f));
            int j;
            if (!indice.TryGetValue(clave, out j)) { j = nuevos.Count; indice[clave] = j; nuevos.Add(vs[i]); }
            mapa[i] = j;
        }
        for (int i = 0; i < ts.Length; i++) ts[i] = mapa[ts[i]];
        vs = nuevos.ToArray();
    }

    ModeloEntorno ModeloPorNombre(string nombre)
    {
        if (modelosEntorno == null) return null;
        foreach (ModeloEntorno m in modelosEntorno.modelos) if (m.nombre == nombre) return m;
        return null;
    }

    MaterialEntorno MaterialDelModelo(string nombre)
    {
        if (!CargarModelosEntorno() || modelosEntorno.materiales == null) return null;
        foreach (MaterialEntorno m in modelosEntorno.materiales) if (m.nombre == nombre) return m;
        return null;
    }

    // ============================================================
    // MATERIALES (de la paleta de modelos.json)
    // ============================================================
    /// Un material de la paleta, opaco, con su color; con 'color' (sRGB),
    /// el de ese objeto. URP Lit sin keywords: sobrevive a la build.
    Material MatEntorno(string nombre, float[] color = null)
    {
        string clave = nombre;
        if (color != null)
            clave += string.Format(CultureInfo.InvariantCulture, "_{0:F3}_{1:F3}_{2:F3}", color[0], color[1], color[2]);
        Material m;
        if (materialesEntorno.TryGetValue(clave, out m) && m != null) return m;
        MaterialEntorno me = MaterialDelModelo(nombre);
        Color c = me != null && me.color != null && me.color.Length >= 3
            ? new Color(me.color[0], me.color[1], me.color[2]) : new Color(0.6f, 0.6f, 0.6f);
        if (color != null && color.Length >= 3) c = new Color(color[0], color[1], color[2]);
        m = new Material(VisorEstructura.ShaderCompatible()) { name = "Entorno_" + clave, color = c };
        FijarSiExiste(m, "_BaseColor", c);
        FijarSiExiste(m, "_Smoothness", me != null ? me.suavidad : 0.3f);
        FijarSiExiste(m, "_Metallic", me != null ? me.metalico : 0f);
        misMateriales.Add(m);
        materialesEntorno[clave] = m;
        return m;
    }

    /// El antepecho, del hormigon visto real (con su textura), o liso.
    Material MaterialAntepecho()
    {
        Material m;
        if (materialesEntorno.TryGetValue("antepecho", out m) && m != null) return m;
        MaterialEntorno me = MaterialDelModelo("antepecho");
        Color c = me != null && me.color != null && me.color.Length >= 3
            ? new Color(me.color[0], me.color[1], me.color[2]) : C_MURO;
        m = NuevoMaterialReal("Entorno_antepecho", "hormigon_visto", c, 0.10f, 0f, Vector2.one);
        if (m == null) return MatEntorno("antepecho");
        materialesEntorno["antepecho"] = m;
        return m;
    }

    /// El vidrio: una copia del asset transparente con el color de la paleta.
    Material MaterialVidrio()
    {
        Material m;
        if (materialesEntorno.TryGetValue("vidrio_fachada", out m) && m != null) return m;
        MaterialEntorno me = MaterialDelModelo("vidrio_fachada");
        Material b = Resources.Load<Material>(RECURSOS + "Mat_vidrio");
        if (b == null)
        {
            Debug.LogWarning("AmbienteVisor: falta Resources/Ambiente/Mat_vidrio (Editor/RecursosRealistas.cs): "
                             + "vidrio opaco.");
            return MatEntorno("vidrio_auto");
        }
        m = new Material(b) { name = "Entorno_vidrio" };
        if (me != null && me.color != null && me.color.Length >= 4)
        {
            var c = new Color(me.color[0], me.color[1], me.color[2], me.color[3]);
            m.color = c;
            FijarSiExiste(m, "_BaseColor", c);
            FijarSiExiste(m, "_Smoothness", me.suavidad);
        }
        misMateriales.Add(m);
        materialesEntorno["vidrio_fachada"] = m;
        return m;
    }
}
