$ErrorActionPreference = 'Stop'
$OutFile = Join-Path $PSScriptRoot 'presence_wiring.kicad_sch'
$script:IdCounter = 1
function New-Id {
    $id = 'a1000000-0000-4000-8000-{0:D12}' -f $script:IdCounter
    $script:IdCounter++
    return $id
}
function F([double]$n) { return [string]::Format([Globalization.CultureInfo]::InvariantCulture, '{0:0.00}', $n) }
function Extract-LibSymbol($libraryFile, $symbolName, $libraryName) {
    $source = [IO.File]::ReadAllText($libraryFile)
    $needle = '(symbol "' + $symbolName + '"'
    $start = $source.IndexOf($needle)
    if ($start -lt 0) { throw "Symbol $symbolName not found in $libraryFile" }
    $depth = 0
    $quoted = $false
    $escaped = $false
    $end = -1
    for ($i = $start; $i -lt $source.Length; $i++) {
        $char = $source[$i]
        if ($quoted) {
            if ($escaped) { $escaped = $false }
            elseif ($char -eq '\\') { $escaped = $true }
            elseif ($char -eq '"') { $quoted = $false }
            continue
        }
        if ($char -eq '"') { $quoted = $true }
        elseif ($char -eq '(') { $depth++ }
        elseif ($char -eq ')') {
            $depth--
            if ($depth -eq 0) { $end = $i; break }
        }
    }
    if ($end -lt 0) { throw "Unclosed symbol definition: $symbolName" }
    $block = $source.Substring($start, $end - $start + 1)
    return $block.Replace($needle, '(symbol "' + $libraryName + ':' + $symbolName + '"')
}
function Property($name, $value, [double]$x, [double]$y, $justify = 'left bottom', $hide = $false) {
    $hideText = if ($hide) { "`n            (hide yes)" } else { '' }
    return @"
        (property `"$name`" `"$value`" (at $(F $x) $(F $y) 0)$hideText
            (effects (font (size 1.27 1.27)) (justify $justify))
        )
"@
}
function Wire([double]$x1, [double]$y1, [double]$x2, [double]$y2) {
    return @"
    (wire (pts (xy $(F $x1) $(F $y1)) (xy $(F $x2) $(F $y2)))
        (stroke (width 0) (type default))
        (uuid `"$(New-Id)`")
    )
"@
}
function NetLabel($name, [double]$x, [double]$y, [int]$angle, $justify) {
    return @"
    (label `"$name`" (at $(F $x) $(F $y) $angle)
        (effects (font (size 1.27 1.27)) (justify $justify))
        (uuid `"$(New-Id)`")
    )
"@
}
function Note($text, [double]$x, [double]$y) {
    return @"
    (text `"$text`" (at $(F $x) $(F $y) 0)
        (effects (font (size 1.1 1.1)) (justify left bottom))
        (uuid `"$(New-Id)`")
    )
"@
}
function Component($libId, $ref, $value, [double]$cx, [double]$cy, $refX, $refY, $valX, $valY, $pins, $projectName, $rootId) {
    $pinInstances = ($pins | ForEach-Object { "        (pin `"$($_.Number)`" (uuid `"$(New-Id)`"))" }) -join "`n"
    $propRef = Property 'Reference' $ref $refX $refY
    $propVal = Property 'Value' $value $valX $valY
    $propFoot = Property 'Footprint' '' $cx $cy 'left bottom' $true
    $propData = Property 'Datasheet' '' $cx $cy 'left bottom' $true
    return @"
    (symbol
        (lib_id `"$libId`")
        (at $(F $cx) $(F $cy) 0)
        (unit 1)
        (exclude_from_sim no)
        (in_bom no)
        (on_board yes)
        (dnp no)
        (uuid `"$(New-Id)`")
$propRef$propVal$propFoot$propData$pinInstances
        (instances (project `"$projectName`"
            (path `"/$rootId`" (reference `"$ref`" ) (unit 1))
        ))
    )
"@
}
function ConnectPins($component, [double]$cx, [double]$cy) {
    $output = ''
    foreach ($pin in $component.Pins) {
        $px = $cx + $pin.X
        $py = $cy - $pin.Y
        switch ($pin.Side) {
            'left'  { $ex = $px - 5.08; $ey = $py; $angle = 180; $justify = 'right bottom' }
            'right' { $ex = $px + 5.08; $ey = $py; $angle = 0; $justify = 'left bottom' }
            'top'   { $ex = $px; $ey = $py - 5.08; $angle = 0; $justify = 'left bottom' }
            'bottom'{ $ex = $px; $ey = $py + 5.08; $angle = 0; $justify = 'left bottom' }
        }
        $output += Wire $px $py $ex $ey
        $output += NetLabel $pin.Net $ex $ey $angle $justify
    }
    return $output
}

$espPins = @(
    @{ Number = '1'; X = -5.08; Y = 5.08; Side = 'left'; Net = '+5V' },
    @{ Number = '2'; X = -5.08; Y = 2.54; Side = 'left'; Net = '+3V3' },
    @{ Number = '3'; X = -5.08; Y = 0.00; Side = 'left'; Net = 'GND' },
    @{ Number = '4'; X = -5.08; Y = -2.54; Side = 'left'; Net = 'ONEWIRE_DQ' },
    @{ Number = '5'; X = -5.08; Y = -5.08; Side = 'left'; Net = 'RADAR_TX' },
    @{ Number = '6'; X = -5.08; Y = -7.62; Side = 'left'; Net = 'RADAR_RX' }
)
$radarPins = @(
    @{ Number = '1'; X = -5.08; Y = 2.54; Side = 'left'; Net = '+5V' },
    @{ Number = '2'; X = -5.08; Y = 0.00; Side = 'left'; Net = 'GND' },
    @{ Number = '3'; X = -5.08; Y = -2.54; Side = 'left'; Net = 'RADAR_RX' },
    @{ Number = '4'; X = -5.08; Y = -5.08; Side = 'left'; Net = 'RADAR_TX' }
)
$dsPins = @(
    @{ Number = '1'; X = -5.08; Y = 2.54; Side = 'left'; Net = 'GND' },
    @{ Number = '2'; X = -5.08; Y = 0.00; Side = 'left'; Net = 'ONEWIRE_DQ' },
    @{ Number = '3'; X = -5.08; Y = -2.54; Side = 'left'; Net = '+3V3' }
)
$rPins = @(
    @{ Number = '1'; X = 0.00; Y = 3.81; Side = 'top'; Net = '+3V3' },
    @{ Number = '2'; X = 0.00; Y = -3.81; Side = 'bottom'; Net = 'ONEWIRE_DQ' }
)

$components = @(
    @{ Lib = 'Connector_Generic:Conn_01x06'; Source = 'Connector_Generic.kicad_sym'; SymbolName = 'Conn_01x06'; Ref = 'J1'; Value = 'ESP32-C3 SuperMini Plus logical pin map'; X = 83.00; Y = 93.00; RefX = 83.00; RefY = 78.00; ValX = 83.00; ValY = 80.50; Pins = $espPins },
    @{ Lib = 'Connector_Generic:Conn_01x04'; Source = 'Connector_Generic.kicad_sym'; SymbolName = 'Conn_01x04'; Ref = 'J2'; Value = 'HLK-LD1125H-24G logical pin map'; X = 215.00; Y = 75.00; RefX = 215.00; RefY = 64.00; ValX = 215.00; ValY = 66.50; Pins = $radarPins },
    @{ Lib = 'Connector_Generic:Conn_01x03'; Source = 'Connector_Generic.kicad_sym'; SymbolName = 'Conn_01x03'; Ref = 'J3'; Value = 'DS18B20 TO-92 pin map'; X = 215.00; Y = 132.00; RefX = 215.00; RefY = 121.00; ValX = 215.00; ValY = 123.50; Pins = $dsPins },
    @{ Lib = 'Device:R'; Source = 'Device.kicad_sym'; SymbolName = 'R'; Ref = 'R1'; Value = '4.7k'; X = 155.00; Y = 132.00; RefX = 160.00; RefY = 128.00; ValX = 160.00; ValY = 130.50; Pins = $rPins }
)

$libText = ''
$libraryDir = Join-Path $env:LOCALAPPDATA 'Programs\KiCad\10.0\share\kicad\symbols'
foreach ($c in $components) {
    $libText += Extract-LibSymbol (Join-Path $libraryDir $c.Source) $c.SymbolName ($c.Lib.Split(':')[0])
    $libText += "`n"
}
$rootId = New-Id
$projectName = 'presence_wiring'
$content = @"
(kicad_sch
    (version 20250610)
    (generator "eeschema")
    (generator_version "10.0")
    (uuid "$rootId")
    (paper "A4")
    (title_block
        (title "ESP32-C3 Presence and Temperature Wiring")
        (date "2026-11-07")
        (rev "1.0")
        (company "ESPHome device")
    )
    (lib_symbols
$libText    )
"@
foreach ($c in $components) {
    $content += Component $c.Lib $c.Ref $c.Value $c.X $c.Y $c.RefX $c.RefY $c.ValX $c.ValY $c.Pins $projectName $rootId
    $content += ConnectPins $c $c.X $c.Y
}
$content += Note 'USB-C cable plugs directly into U1; its 5V pad supplies the radar.' 32 158
$content += Note 'Radar: 5V supply, common GND, 3.3V TTL UART at 115200 baud, 8N1.' 32 162
$content += Note 'J1-J3 use generic pin numbering as logical maps; solder by signal labels/pad markings, not connector position.' 32 166
$content += Note 'DS18B20, flat marked face toward you and leads down: pin 1=GND, pin 2=DQ, pin 3=VDD.' 32 170
$content += Note 'ESPHome pin map: GPIO0=1-Wire; GPIO1=UART RX from radar TX; GPIO3=UART TX to radar RX.' 32 174
$content += Note 'R1 is the required 4.7k pull-up between DQ and 3V3. Do not connect any 5V signal to GPIO.' 32 178
$content += @'
    (embedded_fonts no)
    (sheet_instances (path "/" (page "1")))
)
'@
[System.IO.File]::WriteAllText($OutFile, $content, [System.Text.UTF8Encoding]::new($false))
Write-Output "Wrote $OutFile"
