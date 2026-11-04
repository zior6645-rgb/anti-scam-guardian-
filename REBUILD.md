# Rebuild the source archive

The files in `payload/` are consecutive Base64 chunks of `anti-scam-guardian.tar.xz`.

From the repository root, run:

```bash
cat payload/archive.tar.xz.b64.part* | base64 -d > anti-scam-guardian.tar.xz
tar -xJf anti-scam-guardian.tar.xz
```

On PowerShell:

```powershell
$parts = Get-ChildItem .\payload\archive.tar.xz.b64.part* | Sort-Object Name
$encoded = ($parts | ForEach-Object { Get-Content $_.FullName -Raw }) -join ''
[IO.File]::WriteAllBytes('.\anti-scam-guardian.tar.xz', [Convert]::FromBase64String($encoded))
tar -xJf .\anti-scam-guardian.tar.xz
```

This produces the `anti-scam-guardian/` project directory.
