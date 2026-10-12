import uuid
from types import SimpleNamespace

# Borrado en cascada equivalente a las llaves foráneas de db/schema.sql.
CASCADAS = {
    "concursos": [("criterios", "concurso_id"), ("postores", "concurso_id"),
                  ("documentos_chunks", "concurso_id"), ("dictamenes", "concurso_id")],
    "postores": [("documentos_chunks", "postor_id"), ("dictamenes", "postor_id")],
}
UNICOS = {"postores": ("concurso_id", "ruc")}


class ErrorDeUnicidad(Exception):
    pass


class _Consulta:
    def __init__(self, db: "SupabaseFalso", tabla: str):
        self.db, self.tabla = db, tabla
        self.accion, self.datos = "select", None
        self.filtros, self.orden, self.limite = [], None, None
        self.negar, self.unico = False, False

    def select(self, *_):
        self.accion = "select"
        return self

    def insert(self, datos):
        self.accion, self.datos = "insert", datos
        return self

    def update(self, datos):
        self.accion, self.datos = "update", datos
        return self

    def delete(self):
        self.accion = "delete"
        return self

    @property
    def not_(self):
        self.negar = True
        return self

    def _filtrar(self, condicion):
        negar, self.negar = self.negar, False
        self.filtros.append((lambda fila: not condicion(fila)) if negar else condicion)
        return self

    def eq(self, campo, valor):
        return self._filtrar(lambda fila: fila.get(campo) == valor)

    def in_(self, campo, valores):
        return self._filtrar(lambda fila: fila.get(campo) in valores)

    def order(self, campo, desc=False):
        self.orden = (campo, desc)
        return self

    def limit(self, cantidad):
        self.limite = cantidad
        return self

    def single(self):
        self.unico = True
        return self

    def execute(self):
        filas = self.db.tablas.setdefault(self.tabla, [])

        if self.accion == "insert":
            nuevas = self.datos if isinstance(self.datos, list) else [self.datos]
            creadas = []
            for datos in nuevas:
                fila = {"id": str(uuid.uuid4()), "created_at": self.db.siguiente_marca(), **datos}
                self.db.verificar_unicidad(self.tabla, fila)
                filas.append(fila)
                creadas.append(fila)
            return SimpleNamespace(data=[dict(f) for f in creadas])

        seleccion = [f for f in filas if all(condicion(f) for condicion in self.filtros)]

        if self.accion == "update":
            for fila in seleccion:
                fila.update(self.datos)
            return SimpleNamespace(data=[dict(f) for f in seleccion])

        if self.accion == "delete":
            for fila in seleccion:
                self.db.borrar(self.tabla, fila)
            return SimpleNamespace(data=[dict(f) for f in seleccion])

        if self.orden:
            campo, desc = self.orden
            seleccion = sorted(seleccion, key=lambda f: f.get(campo), reverse=desc)
        if self.limite is not None:
            seleccion = seleccion[:self.limite]
        datos = [dict(f) for f in seleccion]
        return SimpleNamespace(data=datos[0] if self.unico else datos)


class _Bucket:
    def __init__(self, archivos: dict):
        self.archivos = archivos

    def upload(self, path, contenido, opciones=None):
        self.archivos[path] = contenido

    def download(self, path):
        return self.archivos[path]

    def remove(self, paths):
        for path in paths:
            self.archivos.pop(path, None)
        return []


class SupabaseFalso:
    def __init__(self):
        self.tablas: dict[str, list[dict]] = {}
        self.archivos: dict[str, bytes] = {}
        self.storage = SimpleNamespace(from_=lambda _bucket: _Bucket(self.archivos))
        self._marca = 0

    def siguiente_marca(self) -> str:
        self._marca += 1
        return f"2026-01-01T00:00:{self._marca:06d}"

    def table(self, tabla: str) -> _Consulta:
        return _Consulta(self, tabla)

    def verificar_unicidad(self, tabla: str, fila: dict) -> None:
        campos = UNICOS.get(tabla)
        if campos and any(
            all(otra.get(c) == fila.get(c) for c in campos) for otra in self.tablas.get(tabla, [])
        ):
            raise ErrorDeUnicidad(f"{tabla}: valor duplicado en {campos}")

    def borrar(self, tabla: str, fila: dict) -> None:
        if fila in self.tablas.get(tabla, []):
            self.tablas[tabla].remove(fila)
        for hija, llave in CASCADAS.get(tabla, []):
            for dependiente in [f for f in self.tablas.get(hija, []) if f.get(llave) == fila["id"]]:
                self.borrar(hija, dependiente)

    def filas(self, tabla: str) -> list[dict]:
        return self.tablas.get(tabla, [])
