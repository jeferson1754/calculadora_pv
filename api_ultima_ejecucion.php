<?php
header('Content-Type: application/json; charset=utf-8');

$host = 'localhost';
$user = 'root';
$pass = '';
$db   = 'calculadora_pv';

try {
    $pdo = new PDO("mysql:host=$host;dbname=$db;charset=utf8mb4", $user, $pass, [
        PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC
    ]);

   // 1. Obtener la última ejecución
    $sqlUltima = "
        SELECT 
            id,
            LOWER(DATE_FORMAT(fecha_inicio, '%d/%m/%Y %h:%i %p')) AS fecha_inicio,
            duracion_segundos,
            CONCAT(
                FLOOR(duracion_segundos / 60), 'm ', 
                LPAD(MOD(duracion_segundos, 60), 2, '0'), 's'
            ) AS duracion_formateada,
            estado
        FROM historial_ejecuciones
        ORDER BY id DESC
        LIMIT 1
    ";
    $ultima = $pdo->query($sqlUltima)->fetch();

    if (!$ultima) {
        echo json_encode(["status" => "empty", "message" => "Sin ejecuciones"]);
        exit;
    }

    $idActual = $ultima['id'];
    $durActual = (float)$ultima['duracion_segundos'];

    // 2. Obtener el promedio de los últimos 7 días
    $sqlPromedio = "
        SELECT AVG(duracion_segundos) AS prom_seg
        FROM historial_ejecuciones
        WHERE estado = 'EXITOSO'
          AND fecha_inicio >= NOW() - INTERVAL 7 DAY
          AND id != :id_actual
    ";
    $stmtProm = $pdo->prepare($sqlPromedio);
    $stmtProm->execute([':id_actual' => $idActual]);
    $promSemana = $stmtProm->fetchColumn();

    $comparacionSemanal = null;
    if ($promSemana && $promSemana > 0) {
        $diff = round((($durActual - $promSemana) / $promSemana) * 100, 1);
        $comparacionSemanal = [
            'porcentaje' => abs($diff),
            'es_mayor'   => $diff > 0,
            'signo'      => ($diff > 0 ? "+{$diff}%" : "{$diff}%")
        ];
    }

    // 3. Obtener la ejecución anterior inmediata (ayer o último día hábil)
    $sqlAnterior = "
        SELECT 
            CONCAT(
                FLOOR(duracion_segundos / 60), 'm ', 
                LPAD(MOD(duracion_segundos, 60), 2, '0'), 's'
            ) AS duracion_ayer
        FROM historial_ejecuciones
        WHERE estado = 'EXITOSO'
          AND id < :id_actual
        ORDER BY id DESC
        LIMIT 1
    ";
    $stmtAnt = $pdo->prepare($sqlAnterior);
    $stmtAnt->execute([':id_actual' => $idActual]);
    $duracionAyer = $stmtAnt->fetchColumn();

    $ultima['comparacion_semanal'] = $comparacionSemanal;
    $ultima['duracion_ayer'] = $duracionAyer ?: 'N/D';

    echo json_encode(["status" => "success", "data" => $ultima], JSON_UNESCAPED_UNICODE);

} catch (PDOException $e) {
    echo json_encode(["status" => "error", "message" => $e->getMessage()]);
}