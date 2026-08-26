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

    // 1. Obtener Cabeceras de Pedidos
    $sqlCabeceras = "
      SELECT DISTINCT 
            COALESCE(Nombre, '') AS Cliente,
            Pedido,
           `Pos._PD` AS PosPed,
           `RespCtrPr.` AS RespCtrPr,
           Origen,
            Material AS Producto,
            `Ctd.ped.` AS CtdPed,
            `Valor neto` AS ValorNeto,
            `Mon.` AS Moneda,
            `Fecha Probable` AS FechaProbable,
            COALESCE(Estado, 'PRODUCTIVO') AS Estado
        FROM vista_productiva_bom

        UNION ALL

        SELECT DISTINCT 
            COALESCE(Nombre, '') AS Cliente,
            Pedido,
            '' AS PosPed,
            '' AS RespCtrPr,
            '' as Origen,
            Material AS Producto,
            `Ctd.ped.` AS CtdPed,
            `Valor neto` AS ValorNeto,
            `Mon.` AS Moneda,
            `Fecha Probable` AS FechaProbable,
            'REVISIÓN MATERIAL 37' AS Estado
        FROM pedidos_revision_37

        ORDER BY CAST(Pedido AS UNSIGNED) ASC, CAST(PosPed AS UNSIGNED) ASC;
    ";

    $stmt = $pdo->query($sqlCabeceras);
    $cabeceras = $stmt->fetchAll();

 // 2. Obtener Componentes BOM filtrando desde la tabla MySQL
    $sqlBOM = "
        SELECT DISTINCT 
            Pedido,
            `Pos._PD` AS PosPed,
            Material AS Producto,
            `Nivel Explosión` AS NivelExplosion,
            `Pos._BOM` AS PosBOM,
            `N° Componentes` AS Componente,
            `Desc. Componente` AS DescComponente,
            Cantidad AS CantidadBOM,
            UMB,
            Cantidad_Total_Requerida AS CantidadTotal
        FROM vista_productiva_bom
        WHERE `N° Componentes` IN (
            SELECT codigo_material 
            FROM maestro_codigos_32_33
        )
        ORDER BY CAST(NULLIF(`Nivel Explosión`, '') AS UNSIGNED) ASC
    ";
    $stmtBOM = $pdo->query($sqlBOM);
    $componentesRaw = $stmtBOM->fetchAll();

    // Agrupar componentes por Pedido + PosPed
    $mapaBOM = [];
    foreach ($componentesRaw as $comp) {
        $key = $comp['Pedido'] . '_' . $comp['PosPed'];
        $mapaBOM[$key][] = $comp;
    }

    // Vincular componentes
    foreach ($cabeceras as &$row) {
        $key = $row['Pedido'] . '_' . $row['PosPed'];
        $row['componentes'] = isset($mapaBOM[$key]) ? $mapaBOM[$key] : [];
    }

    echo json_encode(["data" => $cabeceras], JSON_UNESCAPED_UNICODE);

} catch (PDOException $e) {
    echo json_encode(["error" => $e->getMessage()]);
}
?>