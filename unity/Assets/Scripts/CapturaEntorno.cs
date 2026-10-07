/*
================================================================
  CapturaEntorno.cs
================================================================
  Fotos de las ventanas, los autos y los arboles, sin tocar la app:

      LaboratorioEstructural.exe -capturarEntorno <carpeta>

  Espera a que el modelo, el relieve y el entorno esten cargados, pone
  la vista realista con el relieve, y saca seis fotos: la del conjunto
  SIN entorno (para comparar), la misma CON entorno, la fachada sur, el
  estacionamiento, las ventanas de cerca y la fachada oeste del LT2. Deja
  un registro.txt con AjustesVista.entornoEstado, lo que dijo
  AmbienteVisor y los errores del log, y cierra la app (codigo 0, o 2 si
  algo falto).

  Misma forma que CapturaRelieve. Mueve solo la camara y las capas. Las
  vistas estan en coordenadas del modelo del CONJUNTO (sincronizar
  conjunto antes); con otro edificio las fotos salen, pero corridas.
  yaw de CamaraOrbital: 0 = la camara al sur (-y del modelo) mirando al
  norte; 90 = al oeste (-x) mirando al este.
================================================================
*/

using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using UnityEngine;

public class CapturaEntorno : MonoBehaviour
{
    const float TOPE_ESPERA_S = 120f;
    const int CALIDAD_JPG = 92;

    public string carpeta;
    private readonly List<string> registro = new List<string>();
    private int nErrores;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void Arrancar()
    {
        string[] args = Environment.GetCommandLineArgs();
        for (int i = 0; i < args.Length - 1; i++)
        {
            if (args[i] != "-capturarEntorno") continue;
            var go = new GameObject("CapturaEntorno");
            go.AddComponent<CapturaEntorno>().carpeta = args[i + 1];
            return;
        }
    }

    void OnEnable() { Application.logMessageReceived += AlLog; }
    void OnDisable() { Application.logMessageReceived -= AlLog; }

    void AlLog(string texto, string pila, LogType tipo)
    {
        if (tipo == LogType.Error || tipo == LogType.Exception || tipo == LogType.Assert)
        {
            nErrores++;
            registro.Add("ERROR del log: " + texto);
        }
        else if (texto.StartsWith("AmbienteVisor:")) registro.Add(texto);
    }

    static bool Listo(string estado, string bueno)
    {
        return !string.IsNullOrEmpty(estado) && (estado.StartsWith(bueno) || estado.StartsWith("Sin "));
    }

    IEnumerator Start()
    {
        Directory.CreateDirectory(carpeta);
        float tope = Time.realtimeSinceStartup + TOPE_ESPERA_S;
        VisorEstructura visor = null;
        CamaraOrbital cam = null;
        while (Time.realtimeSinceStartup < tope)
        {
            visor = visor ?? FindAnyObjectByType<VisorEstructura>();
            cam = cam ?? FindAnyObjectByType<CamaraOrbital>();
            bool relieve = Listo(AjustesVista.relieveEstado, "Relieve del sitio");
            bool entorno = !string.IsNullOrEmpty(AjustesVista.entornoEstado)
                           && !AjustesVista.entornoEstado.StartsWith("Buscando");
            if (visor != null && cam != null && visor.Modelo != null && relieve && entorno) break;
            yield return new WaitForSecondsRealtime(0.5f);
        }
        registro.Add("relieveEstado: " + AjustesVista.relieveEstado);
        registro.Add("entornoEstado: " + AjustesVista.entornoEstado);
        if (visor == null || cam == null || visor.Modelo == null)
        {
            registro.Add("ERROR: no cargo el modelo o la camara antes de " + TOPE_ESPERA_S + " s");
            Escribir();
            Application.Quit(2);
            yield break;
        }
        registro.Add(string.Format("modelo: {0} nodos, {1} elementos", visor.Modelo.nodos.Count,
                                   visor.Modelo.elementos.Count));

        AjustesVista.realista = true;
        AjustesVista.suelo = true;
        AjustesVista.relieve = true;
        AjustesVista.losas = true;
        AjustesVista.ventanas = false;
        AjustesVista.entorno = false;
        EventosVisor.AvisarVistaCambio();
        yield return new WaitForSecondsRealtime(1.5f);
        cam.EncuadrarTodo();
        Vector3 c = cam.centro;
        float d = cam.distancia;
        yield return Foto(cam, "entorno_0_sin_entorno", c, d * 1.7f, 24f, 40f);

        AjustesVista.ventanas = true;
        AjustesVista.entorno = true;
        EventosVisor.AvisarVistaCambio();
        yield return new WaitForSecondsRealtime(1.5f);
        registro.Add("ventanas a la vista: " + Contar("Ventanas") + "; mallas de autos y arboles: "
                     + Contar("Autos y arboles"));
        yield return Foto(cam, "entorno_1_con_entorno", c, d * 1.7f, 24f, 40f);
        // Fachada sur del cuerpo antiguo (y = 47.7), desde el estacionamiento.
        yield return Foto(cam, "entorno_2_fachada_sur", Ejes.AUnity(28f, 47.7f, 1f), 48f, 9f, 10f);
        yield return Foto(cam, "entorno_3_estacionamiento", Ejes.AUnity(48f, 8f, -6f), 62f, 32f, 25f);
        yield return Foto(cam, "entorno_4_ventanas_cerca", Ejes.AUnity(40f, 47.7f, 2f), 15f, 4f, 20f);
        // Fachada oeste del LT2 (x = -24).
        yield return Foto(cam, "entorno_5_fachada_oeste", Ejes.AUnity(-24f, 56f, 0f), 42f, 10f, 100f);

        Escribir();
        bool ok = nErrores == 0 && AjustesVista.entornoEstado.Contains("vanos con ventana");
        Application.Quit(ok ? 0 : 2);
    }

    int Contar(string raiz)
    {
        GameObject go = GameObject.Find(raiz);
        if (go == null) return 0;
        int n = 0;
        foreach (Transform t in go.transform) if (t.gameObject.activeInHierarchy) n++;
        return n;
    }

    IEnumerator Foto(CamaraOrbital cam, string nombre, Vector3 centro, float distancia, float pitch, float yaw)
    {
        const BindingFlags B = BindingFlags.NonPublic | BindingFlags.Public | BindingFlags.Instance;
        typeof(CamaraOrbital).GetField("pitch", B).SetValue(cam, pitch);
        typeof(CamaraOrbital).GetField("yaw", B).SetValue(cam, yaw);
        cam.centro = centro;
        cam.distancia = distancia;
        yield return new WaitForSecondsRealtime(1.5f);
        yield return new WaitForEndOfFrame();
        Texture2D tex = ScreenCapture.CaptureScreenshotAsTexture();
        try { File.WriteAllBytes(Path.Combine(carpeta, nombre + ".jpg"), tex.EncodeToJPG(CALIDAD_JPG)); }
        finally { Destroy(tex); }
        registro.Add(string.Format(System.Globalization.CultureInfo.InvariantCulture,
            "foto {0}: distancia {1:F1} m, pitch {2:F0}, yaw {3:F0}", nombre, distancia, pitch, yaw));
    }

    void Escribir()
    {
        registro.Add("errores del log: " + nErrores);
        File.WriteAllLines(Path.Combine(carpeta, "registro.txt"), registro);
    }
}
