"""Comprueba que el firmware compila, usando una imitación mínima de Arduino (tests/stub_arduino).
No sustituye a compilar para la ESP32 de verdad, pero detecta errores de sintaxis y de tipos."""
import os
import shutil
import subprocess
import tempfile
import unittest

from utilidades import RAIZ

FIRMWARE = os.path.join(RAIZ, "firmware", "controlador_trampillas", "controlador_trampillas.ino")
STUB = os.path.join(RAIZ, "tests", "stub_arduino")


@unittest.skipUnless(shutil.which("g++"), "g++ no está instalado")
class TestFirmware(unittest.TestCase):
    def test_compila_sin_avisos(self):
        with tempfile.TemporaryDirectory() as tmp:
            fuente = os.path.join(tmp, "firmware.cpp")
            with open(FIRMWARE) as f, open(fuente, "w") as g:
                g.write(f.read() + "\nint main(){ setup(); loop(); return 0; }\n")
            binario = os.path.join(tmp, "firmware")
            r = subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-I", STUB, fuente, "-o", binario],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            salida = subprocess.run([binario], capture_output=True, text=True, timeout=5).stdout
            self.assertIn("READY triaje 1", salida)


if __name__ == "__main__":
    unittest.main()
