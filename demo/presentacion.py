"""Prepara las convocatorias de demostración para presentar el sistema, cada una detenida en una etapa.

Hace lo mismo que el comité y los postores en la app (subir documentos, analizar, publicar, postular,
evaluar), con las funciones de la app. Como la cuota gratuita de Gemini no alcanza para todo en un día, cada
convocatoria se lleva hasta la etapa pedida y, si se vuelve a ejecutar, continúa desde donde quedó.

Etapas, en orden:
    ronda_a    revisión de Bases, ronda A analizada (el comité responde los hallazgos en la app)
    ronda_b    ronda A cerrada y ronda B analizada
    matriz     revisión cerrada y matriz armada por el Agente Extractor (en borrador, sin publicar)
    ofertas    convocatoria publicada y con las ofertas de sus tres postores
    evaluada   convocatoria cerrada y postores evaluados (el comité revisa y genera el acta en la app)

Para pasar de una ronda a la siguiente, los hallazgos que sigan pendientes se mantienen con una justificación
que dice que la registró este script; los que el comité ya respondió en la app no se tocan.

Uso:
    python -m demo.presentacion --convocatoria 1 --hasta evaluada
    python -m demo.presentacion --convocatoria 5 --hasta ronda_a
    python -m demo.presentacion --estado          # dónde quedó cada convocatoria y el consumo de hoy
"""
import argparse
from pathlib import Path

from agents.gemini_client import ContextoIA
from agents.extractor import extraer_criterios
from agents.orchestrator import evaluar_postor
from automatizacion import evaluar_registrando
from config import LIMITE_DIARIO_CONSULTAS
from consumo import consultas_de_hoy, estimar_consultas
from db.client import get_client
from demo.datos import CONVOCATORIAS
from rag.ingest import preparar_documento
from rag.pdf_extract import texto_completo
from revision import agente_revisor, servicio
from revision.catalogo import RONDA_A, RONDA_B
from validacion.revision import ARCHIVOS
from views.comite import _guardar_matriz
from views.postor import _nombres_unicos, _registrar_postulacion

CARPETA = Path(__file__).parent / "convocatorias"
ETAPAS = ["ronda_a", "ronda_b", "matriz", "ofertas", "evaluada"]
TITULOS = {
    "convocatoria_1_supervision_agua_potable": "Supervisión de obra de agua potable",
    "convocatoria_2_expediente_centro_de_salud": "Expediente técnico de centro de salud",
    "convocatoria_3_plan_desarrollo_urbano": "Plan de Desarrollo Urbano",
    "convocatoria_4_supervision_canal_de_riego": "Supervisión de canal de riego",
    "convocatoria_5_expediente_puente_vehicular": "Expediente técnico de puente vehicular",
}
FIRMA = "Comité de selección (demostración)"
JUSTIFICACION = ("Registrado por el script de la demostración para continuar con la siguiente etapa: el comité "
                 "mantiene el hallazgo y lo deja constando en el informe.")


class SinCupo(Exception):
    pass


def nombre(c) -> str:
    return f"{c.nomenclatura} · {TITULOS[c.carpeta]}"


def _concurso(c) -> dict | None:
    filas = get_client().table("concursos").select("*").eq("nombre", nombre(c)).limit(1).execute().data
    return filas[0] if filas else None


def etapa_actual(concurso: dict | None) -> int:
    """Índice en ETAPAS de la última etapa terminada (-1 si aún no se analizó la ronda A)."""
    if concurso is None:
        return -1
    if concurso["estado"] == "revision_bases":
        ronda = concurso.get("ronda_revision") or RONDA_A
        analizada = servicio.ultima_revision(concurso["id"], ronda) is not None
        return {RONDA_A: 0 if analizada else -1, RONDA_B: 1 if analizada else 0}[ronda]
    if concurso["estado"] == "borrador":
        return 2
    postores = get_client().table("postores").select("estado").eq("concurso_id", concurso["id"]).execute().data
    if concurso["estado"] == "abierto" or any(p["estado"] in ("recibido", "evaluando", "error") for p in postores):
        return 3 if postores else 2
    return 4


def _con_cupo(necesarias: int, que: str) -> None:
    usadas = consultas_de_hoy()
    if usadas + necesarias > LIMITE_DIARIO_CONSULTAS:
        raise SinCupo(f"{que} necesita unas {necesarias} consultas; hoy van {usadas} de {LIMITE_DIARIO_CONSULTAS}. "
                      "Continúa mañana con el mismo comando.")


def _subir(concurso: dict, archivos: list[tuple[str, Path]]) -> None:
    for tipo, ruta in archivos:
        print(f"  subiendo {ruta.name}")
        servicio.subir_documento(concurso["id"], tipo, ruta.name, ruta.read_bytes())


def _analizar(concurso: dict, ronda: str) -> None:
    estimadas = agente_revisor.consultas_estimadas(ronda, servicio.documentos_revisables(concurso["id"]))
    _con_cupo(estimadas, f"La ronda {ronda}")
    print(f"  analizando la ronda {ronda} (unas {estimadas} consultas)")
    servicio.revisar(concurso["id"], ronda, con_agente=True)
    hallazgos = servicio.hallazgos(concurso["id"], ronda)
    print(f"  {len(hallazgos)} hallazgo(s): " + ", ".join(sorted(h["codigo"] for h in hallazgos)))


def _cerrar_ronda(concurso: dict, ronda: str) -> None:
    for hallazgo in servicio.hallazgos(concurso["id"], ronda):
        if hallazgo["estado"] == "pendiente":
            servicio.mantener(hallazgo["id"], JUSTIFICACION, FIRMA)
    listo, motivo = servicio.puede_continuar(concurso["id"], ronda)
    if not listo:
        raise RuntimeError(f"No se puede cerrar la ronda {ronda}: {motivo}")


def ronda_a(c, concurso: dict | None) -> dict:
    if concurso is None:
        concurso = get_client().table("concursos").insert({
            "nombre": nombre(c), "estado": "revision_bases", "ronda_revision": RONDA_A,
            "descripcion": f"{c.objeto}. Convocatoria de demostración: entidad, postores y montos son ficticios.",
        }).execute().data[0]
    origen = CARPETA / c.carpeta / "revision_de_bases"
    vigentes = servicio.documentos_vigentes(concurso["id"])
    _subir(concurso, [(t, origen / n) for t, n in ARCHIVOS[RONDA_A].items() if t not in vigentes])
    _analizar(concurso, RONDA_A)
    return concurso


def ronda_b(c, concurso: dict) -> dict:
    if (concurso.get("ronda_revision") or RONDA_A) == RONDA_A:
        _cerrar_ronda(concurso, RONDA_A)
        get_client().table("concursos").update({"ronda_revision": RONDA_B}).eq("id", concurso["id"]).execute()
    origen = CARPETA / c.carpeta
    vigentes = servicio.documentos_vigentes(concurso["id"])
    archivos = [("pliego", origen / "revision_de_bases" / ARCHIVOS[RONDA_B]["pliego"]),
                ("bases_integradas", next(origen.glob("Bases Integradas *.pdf")))]
    _subir(concurso, [(t, r) for t, r in archivos if t not in vigentes])
    _analizar(concurso, RONDA_B)
    return concurso


def matriz(c, concurso: dict) -> dict:
    """Como «Cerrar la revisión y armar la matriz»: las Bases Integradas revisadas pasan a ser las del concurso."""
    _cerrar_ronda(concurso, RONDA_B)
    _con_cupo(3, "La matriz")
    documento = servicio.bases_de_la_ronda(concurso["id"], RONDA_B)
    get_client().table("concursos").update({"bases_pdf_path": documento["path"], "estado": "borrador"}).eq(
        "id", concurso["id"]).execute()
    print("  el Agente Extractor arma la matriz")
    resultado = extraer_criterios(texto_completo(documento.get("paginas") or []), ContextoIA("extractor", concurso["id"]))
    criterios = [{**criterio, "orden": orden} for orden, criterio in enumerate(resultado.criterios)]
    _guardar_matriz(concurso["id"], criterios, resultado.puntaje_minimo)
    print(f"  {len(criterios)} criterios; los factores suman {resultado.suma_factores:g} puntos")
    return concurso


def ofertas(c, concurso: dict) -> dict:
    get_client().table("concursos").update({"estado": "abierto"}).eq("id", concurso["id"]).execute()
    registrados = {p["ruc"] for p in get_client().table("postores").select("ruc").eq("concurso_id", concurso["id"])
                   .execute().data}
    for oferta in c.ofertas:
        if oferta.ruc in registrados:
            continue
        rutas = sorted((CARPETA / c.carpeta / oferta.carpeta).glob("*.pdf"))
        print(f"  postula {oferta.razon_social} ({len(rutas)} archivos)")
        archivos = list(zip(_nombres_unicos([r.name for r in rutas]), (r.read_bytes() for r in rutas)))
        lector = ContextoIA("lector", concurso["id"])
        documentos = [preparar_documento(contenido, lector, nombre_archivo) for nombre_archivo, contenido in archivos]
        _registrar_postulacion(concurso["id"], oferta.ruc, oferta.razon_social, archivos, documentos)
    return concurso


def evaluada(c, concurso: dict) -> dict:
    client = get_client()
    client.table("concursos").update({"estado": "cerrado"}).eq("id", concurso["id"]).execute()
    criterios = len(client.table("criterios").select("id").eq("concurso_id", concurso["id"]).execute().data)
    pendientes = client.table("postores").select("*").eq("concurso_id", concurso["id"]).in_(
        "estado", ["recibido", "error"]).execute().data
    for postor in sorted(pendientes, key=lambda p: p["razon_social"]):
        _con_cupo(estimar_consultas(criterios), f"Evaluar a {postor['razon_social']}")
        print(f"  evaluando a {postor['razon_social']}")
        evaluar_registrando(postor, evaluar_postor)
    return concurso


PASOS = {"ronda_a": ronda_a, "ronda_b": ronda_b, "matriz": matriz, "ofertas": ofertas, "evaluada": evaluada}


def preparar(c, hasta: str) -> None:
    concurso = _concurso(c)
    hecha = etapa_actual(concurso)
    print(f"{nombre(c)}: " + (f"está en «{ETAPAS[hecha]}»" if hecha >= 0 else "por empezar")
          + f"; se lleva hasta «{hasta}».")
    for etapa in ETAPAS[hecha + 1:ETAPAS.index(hasta) + 1]:
        print(f"- {etapa}")
        concurso = PASOS[etapa](c, concurso)
        concurso = _concurso(c)
    print(f"Listo. Consultas de hoy: {consultas_de_hoy()} de {LIMITE_DIARIO_CONSULTAS}.")


def estado() -> None:
    for numero, c in enumerate(CONVOCATORIAS, 1):
        hecha = etapa_actual(_concurso(c))
        print(f"{numero}. {nombre(c)}: " + (ETAPAS[hecha] if hecha >= 0 else "sin empezar"))
    print(f"Consultas de hoy: {consultas_de_hoy()} de {LIMITE_DIARIO_CONSULTAS}.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--convocatoria", type=int, choices=range(1, len(CONVOCATORIAS) + 1))
    parser.add_argument("--hasta", choices=ETAPAS)
    parser.add_argument("--estado", action="store_true")
    argumentos = parser.parse_args()
    if argumentos.estado or not argumentos.convocatoria:
        estado()
        return
    try:
        preparar(CONVOCATORIAS[argumentos.convocatoria - 1], argumentos.hasta or ETAPAS[-1])
    except SinCupo as e:
        print(f"Se detuvo: {e}")


if __name__ == "__main__":
    main()
