/*
 * Graficos del dashboard del gerente (Chart.js via CDN).
 * Los datos (DATOS_GRAFICOS) los calcula el backend con datos reales -
 * ver app/controllers/gerente/dashboard.py - este archivo solo los dibuja.
 */
document.addEventListener('DOMContentLoaded', function () {
    if (typeof Chart === 'undefined' || typeof DATOS_GRAFICOS === 'undefined') return;

    const PALETA = ['#1a7504', '#22a005', '#f0ad4e', '#dc3545', '#0d6efd', '#6c757d'];

    function crear(idCanvas, config) {
        const elemento = document.getElementById(idCanvas);
        if (!elemento) return;
        new Chart(elemento, config);
    }

    const porEstado = DATOS_GRAFICOS.prestamos_estado || {};
    crear('grafico-prestamos-estado', {
        type: 'doughnut',
        data: {
            labels: ['Activos', 'Vencidos', 'Devueltos'],
            datasets: [{
                data: [porEstado.activo || 0, porEstado.vencido || 0, porEstado.devuelto || 0],
                backgroundColor: ['#1a7504', '#dc3545', '#6c757d'],
            }],
        },
        options: { responsive: true, plugins: { legend: { position: 'bottom' } } },
    });

    const librosPrestados = DATOS_GRAFICOS.libros_mas_prestados || { labels: [], valores: [] };
    crear('grafico-libros-prestados', {
        type: 'bar',
        data: {
            labels: librosPrestados.labels,
            datasets: [{ label: 'Préstamos', data: librosPrestados.valores, backgroundColor: '#1a7504' }],
        },
        options: {
            responsive: true,
            indexAxis: 'y',
            plugins: { legend: { display: false } },
            scales: { x: { beginAtZero: true, ticks: { precision: 0 } } },
        },
    });

    const porPeriodo = DATOS_GRAFICOS.prestamos_por_mes || { labels: [], valores: [] };
    crear('grafico-prestamos-periodo', {
        type: 'line',
        data: {
            labels: porPeriodo.labels,
            datasets: [{
                label: 'Préstamos',
                data: porPeriodo.valores,
                borderColor: '#1a7504',
                backgroundColor: 'rgba(26, 117, 4, 0.15)',
                tension: 0.25,
                fill: true,
            }],
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
        },
    });

    const deudores = DATOS_GRAFICOS.top_deudores || { labels: [], valores: [] };
    crear('grafico-top-deudores', {
        type: 'bar',
        data: {
            labels: deudores.labels,
            datasets: [{ label: 'Monto adeudado ($)', data: deudores.valores, backgroundColor: PALETA }],
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: true } },
        },
    });
});
