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

    $metodo = $_SERVER['REQUEST_METHOD'];

    // --- LEER PARÁMETROS (GET) ---
    if ($metodo === 'GET') {
        $stmt = $pdo->query("SELECT clave, valor FROM parametros_configuracion WHERE clave IN ('FECHA_DESDE', 'FECHA_HASTA')");
        $filas = $stmt->fetchAll();
        
        $parametros = [];
        foreach ($filas as $f) {
            $parametros[$f['clave']] = $f['valor'];
        }

        echo json_encode(["status" => "success", "data" => $parametros]);
        exit;
    }

    // --- GUARDAR PARÁMETROS (POST) ---
    if ($metodo === 'POST') {
        $fecha_desde = $_POST['fecha_desde'] ?? null;
        $fecha_hasta = $_POST['fecha_hasta'] ?? null;

        if (!$fecha_desde || !$fecha_hasta) {
            echo json_encode(["status" => "error", "message" => "Ambas fechas son obligatorias."]);
            exit;
        }

        // Convertir formato HTML (YYYY-MM-DD) a formato estándar SAP (DD.MM.YYYY)
        $fd_sap = date('d.m.Y', strtotime($fecha_desde));
        $fh_sap = date('d.m.Y', strtotime($fecha_hasta));

        $sql = "UPDATE parametros_configuracion SET valor = :valor WHERE clave = :clave";
        
        $stmt = $pdo->prepare($sql);
        $stmt->execute([':valor' => $fd_sap, ':clave' => 'FECHA_DESDE']);
        $stmt->execute([':valor' => $fh_sap, ':clave' => 'FECHA_HASTA']);

        echo json_encode([
            "status" => "success", 
            "message" => "Fechas actualizadas correctamente en la BD.",
            "fecha_desde_sap" => $fd_sap,
            "fecha_hasta_sap" => $fh_sap
        ]);
        exit;
    }

} catch (PDOException $e) {
    echo json_encode(["status" => "error", "message" => $e->getMessage()]);
}
?>