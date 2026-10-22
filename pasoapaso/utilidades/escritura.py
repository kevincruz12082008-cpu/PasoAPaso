import ctypes
import struct
from ctypes import wintypes

ENTRADA_TECLADO = 1
TECLA_UNICODE = 0x0004
TECLA_SOLTAR = 0x0002


class _Raton(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("datos", wintypes.DWORD),
        ("banderas", wintypes.DWORD),
        ("tiempo", wintypes.DWORD),
        ("extra", ctypes.c_size_t),
    ]


class _Teclado(ctypes.Structure):
    _fields_ = [
        ("virtual", wintypes.WORD),
        ("escaneo", wintypes.WORD),
        ("banderas", wintypes.DWORD),
        ("tiempo", wintypes.DWORD),
        ("extra", ctypes.c_size_t),
    ]


class _Hardware(ctypes.Structure):
    _fields_ = [
        ("mensaje", wintypes.DWORD),
        ("bajo", wintypes.WORD),
        ("alto", wintypes.WORD),
    ]


class _Union(ctypes.Union):
    _fields_ = [("raton", _Raton), ("teclado", _Teclado), ("hardware", _Hardware)]


class _Entrada(ctypes.Structure):
    _fields_ = [("tipo", wintypes.DWORD), ("union", _Union)]


def escribir_caracter(caracter):
    codificado = caracter.encode("utf-16-le")
    unidades = struct.unpack("<%dH" % (len(codificado) // 2), codificado)
    entradas = (_Entrada * (len(unidades) * 2))()
    posicion = 0
    for unidad in unidades:
        for banderas in (TECLA_UNICODE, TECLA_UNICODE | TECLA_SOLTAR):
            entradas[posicion].tipo = ENTRADA_TECLADO
            entradas[posicion].union.teclado = _Teclado(0, unidad, banderas, 0, 0)
            posicion += 1
    ctypes.windll.user32.SendInput(
        len(entradas), ctypes.byref(entradas), ctypes.sizeof(_Entrada)
    )
