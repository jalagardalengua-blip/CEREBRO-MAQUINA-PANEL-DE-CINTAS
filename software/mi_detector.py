"""
AQUÍ VA TU SOFTWARE DE DETECCIÓN.

Solo tienes que rellenar estas dos funciones. El servicio de línea (linea.py)
y el ejemplo (ejemplo_detector.py) las llaman por cada foto.
"""
import random


def capturar_imagen(num_foto):
    """Devuelve la imagen que la cámara tomó con el disparo `num_foto`.
    Con disparo hardware, la cámara hace la foto sola al recibir el pulso; aquí solo la recoges.
    Ejemplo con OpenCV:  ok, img = camara.read(); return img
    """
    return None


def detectar(imagen, demo=False):
    """Tu modelo. Devuelve una lista de frutas, cada una un dict con:
        x, y        centro de la fruta en píxeles
        mala        True si tiene defecto
        confianza   de 0 a 1
        defecto     (opcional) texto: "podrido", "golpe", "mancha"...
    """
    if not demo:
        raise NotImplementedError("Conecta aquí tu modelo de detección (mi_detector.py)")
    # Modo demo: inventa frutas para probar la conexión.
    frutas = []
    for _ in range(random.randint(2, 6)):
        mala = random.random() < 0.1
        frutas.append({"x": random.uniform(300, 980), "y": random.uniform(10, 710),
                       "mala": mala,
                       "confianza": random.uniform(0.6, 0.8) if random.random() < 0.03 else random.uniform(0.85, 1.0),
                       "defecto": random.choice(["podrido", "golpe", "mancha"]) if mala else None})
    return frutas
