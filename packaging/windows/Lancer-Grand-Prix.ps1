[CmdletBinding()]
param(
 [int]$Index=-1,
 [ValidateRange(1,60)][int]$Fps=20
)
$ErrorActionPreference='Stop'
$indexValue=$Index
if ($indexValue -lt 0) {
  $raw=Read-Host 'Parcours canonique (0 a 11, Entree = 5)'
  if ([string]::IsNullOrWhiteSpace($raw)) { $raw='5' }
  if ($raw -cnotmatch '^(?:[0-9]|10|11)$') { throw 'Parcours invalide.' }
  $indexValue=[int]$raw
}
if (-not $PSBoundParameters.ContainsKey('Fps')) {
  # Windows PowerShell 5.1 (STA) slider, never an in-flight scene mutation.
  # Explicit -Fps stays noninteractive for scripted runs and CI.
  Add-Type -AssemblyName System.Windows.Forms
  Add-Type -AssemblyName System.Drawing
  $form = New-Object System.Windows.Forms.Form
  $form.Text = 'Grand Prix - rendu 3D'
  $form.StartPosition = 'CenterScreen'
  $form.ClientSize = [System.Drawing.Size]::new(430, 160)
  $form.FormBorderStyle = 'FixedDialog'
  $form.MaximizeBox = $false
  $track = New-Object System.Windows.Forms.TrackBar
  $track.Minimum = 1
  $track.Maximum = 60
  $track.Value = 20
  $track.SmallChange = 1
  $track.LargeChange = 5
  $track.TickFrequency = 5
  $track.Left = 15
  $track.Top = 45
  $track.Width = 400
  $display = New-Object System.Windows.Forms.Label
  $display.Left = 15
  $display.Top = 15
  $display.Width = 400
  $display.Text = 'Rendu 3D : 20 FPS (physique : 8 ms)'
  $track.add_ValueChanged({
    $display.Text = ('Rendu 3D : {0} FPS (physique : 8 ms)' -f $track.Value)
  })
  $ok = New-Object System.Windows.Forms.Button
  $ok.Text = 'Demarrer'
  $ok.Left = 240
  $ok.Top = 115
  $ok.Width = 80
  $ok.DialogResult = [System.Windows.Forms.DialogResult]::OK
  $cancel = New-Object System.Windows.Forms.Button
  $cancel.Text = 'Annuler'
  $cancel.Left = 330
  $cancel.Top = 115
  $cancel.Width = 80
  $cancel.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
  $form.Controls.AddRange(@($display, $track, $ok, $cancel))
  $form.AcceptButton = $ok
  $form.CancelButton = $cancel
  try {
    if ($form.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) {
      throw 'Lancement annule.'
    }
    $Fps = [int]$track.Value
  }
  finally { $form.Dispose() }
}
$env:WEBEEBLOCKS_GP_INDEX=[string]$indexValue
$env:WEBEEBLOCKS_GP_FPS=[string]$Fps
Write-Host ("Grand Prix canonique {0:D2}, rendu natif plafond {1} FPS, physique 8 ms." -f $indexValue,$Fps)
& (Join-Path $PSScriptRoot 'Launch-WebeeBlocks.cmd')
exit $LASTEXITCODE
