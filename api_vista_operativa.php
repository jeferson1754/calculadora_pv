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

    // Detectar si la petición solicita únicamente la vista de Códigos 37
    $tipoConsulta = isset($_GET['tipo']) ? trim($_GET['tipo']) : 'completo';

    if ($tipoConsulta === 'solo_37') {
        // 1. Obtener Cabeceras de Pedidos
        $sqlCabeceras = "
        SELECT DISTINCT 
                COALESCE(Nombre, '') AS Cliente,
                Pedido,
                    `Texto breve de material` as texto_breve,
            `Pos._PD` AS PosPed,
            `RCtrP` AS RespCtrPr,
            Origen,
                Material AS Producto,
                `Ctd.ped.` AS CtdPed,
                `Valor neto` AS ValorNeto,
                `Mon.` AS Moneda,
                `Fecha Probable` AS FechaProbable,
                COALESCE(Estado, 'PRODUCTIVO') AS Estado,
                Motivo_Rechazo
            FROM vista_productiva_bom
            WHERE Estado != 'RECHAZADO'
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
                SELECT codigo_material COLLATE utf8mb4_general_ci 
                FROM maestro_codigos_32_33
            )
            -- REGLA 32 vs 33 EXCLUSIVA PARA TUBERÍAS ('TU AC '):
            -- Si existe un código 32 de tubería ('TU AC %'), se excluye el código 33 de tubería ('TU AC %') en la misma posición del pedido
            AND NOT (
                `N° Componentes` LIKE '33%' 
                AND `Desc. Componente` LIKE 'TU AC %'
                AND EXISTS (
                    SELECT 1 
                    FROM vista_productiva_bom padre
                    WHERE padre.Pedido = vista_productiva_bom.Pedido
                    AND padre.`Pos._PD` = vista_productiva_bom.`Pos._PD`
                    AND padre.`N° Componentes` LIKE '32%'
                    AND padre.`Desc. Componente` LIKE 'TU AC %'
                )
            )
        ";
    } else {

        $sqlCabeceras = "
SELECT DISTINCT 
    COALESCE(v.Nombre, '') AS Cliente,
    v.Pedido,
    v.`Texto breve de material` AS texto_breve,
    -- Si el pedido tiene un rechazo registrado, sobreescribe la posición; si no, deja la original
    COALESCE(NULLIF(h.posicion, ''), v.`Pos._PD`) AS PosPed,
    v.`RCtrP` AS RespCtrPr,
    v.Origen,
    -- Si el pedido tiene un rechazo registrado, sobreescribe el material; si no, deja el original
    COALESCE(NULLIF(h.material, ''), v.Material) AS Producto,
    v.`Ctd.ped.` AS CtdPed,
    v.`Valor neto` AS ValorNeto,
    v.`Mon.` AS Moneda,
    v.`Fecha Probable` AS FechaProbable,
    -- Estado: pasa a RECHAZADO si existe motivo
    CASE 
        WHEN COALESCE(NULLIF(TRIM(v.Motivo_Rechazo), ''), NULLIF(TRIM(h.motivo_rechazo), '')) IS NOT NULL 
        THEN 'RECHAZADO'
        ELSE COALESCE(v.Estado, 'PRODUCTIVO')
    END AS Estado,
    -- Motivo de rechazo consolidado
    COALESCE(NULLIF(TRIM(v.Motivo_Rechazo), ''), TRIM(h.motivo_rechazo), '') AS Motivo_Rechazo

FROM vista_productiva_bom v
LEFT JOIN (
    -- Busca el último rechazo por número de pedido (independiente de la posición original de la vista)
    SELECT pedido, posicion, material, motivo_rechazo
    FROM historial_rechazados_va03
    WHERE id IN (
        SELECT MAX(id)
        FROM historial_rechazados_va03
        GROUP BY pedido
    )
) h ON TRIM(LEADING '0' FROM v.Pedido) = TRIM(LEADING '0' FROM h.pedido)

UNION ALL

SELECT DISTINCT 
    COALESCE(Nombre, '') AS Cliente,
    Pedido,
    '' AS texto_breve,
    '' AS PosPed,
    '' AS RespCtrPr,
    '' AS Origen,
    Material AS Producto,
    `Ctd.ped.` AS CtdPed,
    `Valor neto` AS ValorNeto,
    `Mon.` AS Moneda,
    `Fecha Probable` AS FechaProbable,
    'REVISIÓN MATERIAL 37' AS Estado,
    '' AS Motivo_Rechazo
FROM pedidos_revision_37

ORDER BY 
    CAST(Pedido AS UNSIGNED) ASC, 
    CAST(NULLIF(PosPed, '') AS UNSIGNED) ASC;
        ";

        $stmt = $pdo->query($sqlCabeceras);
        $cabeceras = $stmt->fetchAll();

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
        ";
    }

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
