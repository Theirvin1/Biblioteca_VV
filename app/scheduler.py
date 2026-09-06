import time
from app import create_app
from app.extensions import db

app = create_app()


def obtener_intervalo_horas():
    """Lee desde configuracion_sistema cada cuántas horas debe ejecutarse la tarea."""
    with app.app_context():
        resultado = db.session.execute(
            db.text("SELECT valor FROM configuracion_sistema WHERE clave = 'intervalo_verificacion_horas'")
        ).fetchone()

        if resultado is None:
            return 24  # valor por defecto si no existe la clave

        try:
            return float(resultado[0])
        except (ValueError, TypeError):
            return 24


def actualizar_prestamos_vencidos():
    """Ejecuta la función SQL que marca los préstamos vencidos."""
    with app.app_context():
        db.session.execute(db.text("SELECT fn_actualizar_estado_vencido()"))
        db.session.commit()
        print("Verificación de préstamos vencidos ejecutada.")


def iniciar_scheduler():
    print("Scheduler de tareas programadas iniciado...")
    while True:
        actualizar_prestamos_vencidos()
        horas_espera = obtener_intervalo_horas()
        print(f"Próxima verificación en {horas_espera} horas.")
        time.sleep(horas_espera * 3600)


if __name__ == '__main__':
    iniciar_scheduler()