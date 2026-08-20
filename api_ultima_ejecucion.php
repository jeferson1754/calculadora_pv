<?php
header('Content-Type: application/json; charset=utf-8');

$host = 'localhost';
$user = 'root';
$pass = '';
$db   = 'calculadora_pv';

try {
    $pdo = new PDO("mysql:host=$host;dbname=$db;charset=utf8mb4", $user, $pass, [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC
    ]);

    // Obtener únicamente el último registro de la tabla historial_ejecuciones
    $sql = "
        SELECT 
            id,
            DATE_FORMAT(fecha_inicio, '%d/%m/%Y %H:%i:%s') AS fecha_inicio,
            DATE_FORMAT(fecha_fin, '%d/%m/%Y %H:%i:%s') AS fecha_fin,
            CONCAT(duracion_segundos, 's') AS duracion,
            modulo,
            estado,
            registros_procesados,
            COALESCE(mensaje_error, '') AS error
        FROM historial_ejecuciones
        ORDER BY id DESC
        LIMIT 1
    ";

    $stmt = $pdo->query($sql);
    $ultima = $stmt->fetch();

    if ($ultima) {
        echo json_encode(["status" => "success", "data" => $ultima], JSON_UNESCAPED_UNICODE);
    } else {
        echo json_encode(["status" => "empty", "message" => "Sin ejecuciones registradas"]);
    }

} catch (PDOException $e) {
    echo json_encode(["status" => "error", "message" => $e->getMessage()]);
}
?>