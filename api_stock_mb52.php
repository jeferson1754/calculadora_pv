<?php

/**
 * api_stock_mb52.php
 * Entrega el stock libre de utilización (MB52) por material y almacén,
 * con la descripción del material (MM60) y el valor total de stock (Valor_Total).
 *
 * Respuesta:
 * { "status":"success", "data":[ {Material, Descripcion, UMB, Almacen, Tipo, EsTransito,
 *                                 Computable, StockLibre, ValorTotal, ValorUnitario}, ... ] }
 *
 * ValorUnitario = ValorTotal / StockLibre (por almacén, en la UMB de SAP).
 * El front recalcula un valor unitario ponderado por material en la UMB homologada.
 */

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');

/* =====================================================================
   1. CONFIGURACIÓN  (AJUSTAR A TU BASE DE DATOS)
   ===================================================================== */

$DB = [
    'host'    => 'localhost',
    'dbname'  => 'calculadora_pv',
    'user'    => 'root',
    'pass'    => '',
    'charset' => 'utf8mb4',
];

// Tablas y columnas donde guardas lo extraído de SAP
$T_STOCK = [
    'tabla'       => 'maestro_bodegas',   // extracción MB52
    'material'    => 'Componente',
    'almacen'     => 'Almacén',
    'umb'         => 'UMB',
    'stock_libre' => 'Stock_Libre',       // "Libre utilización"
    'valor_total' => 'Valor_Total',       // Valor del stock
];

$T_MAT = [
    'tabla'       => 'maestro_codigos_32_33',   // extracción MM60 (descripciones)
    'material'    => 'codigo_material',
    'descripcion' => 'descripcion',
];

// Almacenes productivos que SÍ suman al stock total disponible
$BODEGAS_CONFORMES = ['1001', '1014'];
// Almacenes de despunte
$BODEGAS_DESPUNTES = ['1010'];
// Almacenes en tránsito: se muestran pero NO suman al stock disponible total
$BODEGAS_TRANSITO  = ['1027', '1029', '1030', '1032'];
// Almacenes excluidos por completo
$BODEGAS_EXCLUIDAS = ['1018', '1003'];

// Prefijos de materias primas permitidas (diccionario) y excluidos
$PREFIJOS_MP        = ['33', '32'];
$PREFIJOS_EXCLUIDOS = ['37'];

/* =====================================================================
   2. UTILIDADES
   ===================================================================== */

/** Convierte números SAP ("1.234,56", "1234.5", "1.234,56-") a float */
function parseNumSap($v)
{
    if ($v === null || $v === '') return 0.0;
    $s = trim((string)$v);
    $negativo = false;
    if (substr($s, -1) === '-') {
        $negativo = true;
        $s = substr($s, 0, -1);
    }
    if (strpos($s, ',') !== false) {
        $s = str_replace('.', '', $s);
        $s = str_replace(',', '.', $s);
    }
    $n = (float)$s;
    return $negativo ? -$n : $n;
}

function limpiarCodigo($c)
{
    return ltrim(trim((string)$c), '0');
}

function empiezaCon($codigo, array $prefijos)
{
    foreach ($prefijos as $p) {
        if (strpos($codigo, $p) === 0) return true;
    }
    return false;
}

function responder($payload, $http = 200)
{
    http_response_code($http);
    echo json_encode($payload, JSON_UNESCAPED_UNICODE);
    exit;
}

/* =====================================================================
   3. CONSULTA
   ===================================================================== */
try {
    $pdo = new PDO(
        "mysql:host={$DB['host']};dbname={$DB['dbname']};charset={$DB['charset']}",
        $DB['user'],
        $DB['pass'],
        [
            PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        ]
    );

    $bodegasValidas = array_values(array_diff(
        array_merge($BODEGAS_CONFORMES, $BODEGAS_DESPUNTES, $BODEGAS_TRANSITO),
        $BODEGAS_EXCLUIDAS
    ));

    if (empty($bodegasValidas)) {
        responder(['status' => 'success', 'data' => []]);
    }

    $in = implode(',', array_fill(0, count($bodegasValidas), '?'));

    $sql = "
        SELECT
            s.`{$T_STOCK['material']}`    AS Material,
            s.`{$T_STOCK['almacen']}`     AS Almacen,
            s.`{$T_STOCK['umb']}`         AS UMB,
            s.`{$T_STOCK['stock_libre']}` AS StockLibre,
            s.`{$T_STOCK['valor_total']}` AS ValorTotal,
            m.`{$T_MAT['descripcion']}`   AS Descripcion
        FROM `{$T_STOCK['tabla']}` s
        LEFT JOIN `{$T_MAT['tabla']}` m
               ON TRIM(LEADING '0' FROM m.`{$T_MAT['material']}`) = TRIM(LEADING '0' FROM s.`{$T_STOCK['material']}`) COLLATE utf8mb4_unicode_ci
        WHERE TRIM(s.`{$T_STOCK['almacen']}`) IN ($in)
    ";

    $stmt = $pdo->prepare($sql);
    $stmt->execute($bodegasValidas);

    /* -----------------------------------------------------------------
       Agrupar por Material + Almacén
       ----------------------------------------------------------------- */
    $agrupado = [];

    while ($r = $stmt->fetch()) {
        $material = limpiarCodigo($r['Material']);
        if ($material === '') continue;

        if (!empiezaCon($material, $PREFIJOS_MP))        continue;
        if (empiezaCon($material, $PREFIJOS_EXCLUIDOS))  continue;

        $almacen = trim((string)$r['Almacen']);
        $clave   = $material . '|' . $almacen;

        if (!isset($agrupado[$clave])) {
            $esTransito = in_array($almacen, $BODEGAS_TRANSITO, true);
            $tipo = 'CONFORME';
            if ($esTransito) {
                $tipo = 'TRANSITO';
            } elseif (in_array($almacen, $BODEGAS_DESPUNTES, true)) {
                $tipo = 'DESPUNTE';
            }

            $agrupado[$clave] = [
                'Material'    => $material,
                'Descripcion' => trim((string)($r['Descripcion'] ?? '')),
                'UMB'         => strtoupper(trim((string)$r['UMB'])),
                'Almacen'     => $almacen,
                'Tipo'        => $tipo,
                'EsTransito'  => $esTransito,
                'Computable'  => !$esTransito,
                'StockLibre'  => 0.0,
                'ValorTotal'  => 0.0,
            ];
        }
        $agrupado[$clave]['StockLibre'] += parseNumSap($r['StockLibre']);
        $agrupado[$clave]['ValorTotal'] += parseNumSap($r['ValorTotal']);
    }

    // Redondeo final y valor unitario por almacén
    $data = array_map(function ($f) {
        $f['StockLibre']    = round($f['StockLibre'], 3);
        $f['ValorTotal']    = round($f['ValorTotal'], 2);
        $f['ValorUnitario'] = $f['StockLibre'] > 0 ? round($f['ValorTotal'] / $f['StockLibre'], 4) : 0;
        return $f;
    }, array_values($agrupado));

    responder(['status' => 'success', 'total' => count($data), 'data' => $data]);
} catch (Throwable $e) {
    error_log('[api_stock_mb52] ' . $e->getMessage());
    responder(['status' => 'error', 'message' => 'Error al consultar el stock MB52.'], 500);
}