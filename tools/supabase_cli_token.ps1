# supabase_cli_token.ps1 - print the access token the Supabase CLI holds in the Windows credential store (2026-10-26).
# `supabase login` keeps it there (target "Supabase CLI:supabase"); the post-deploy smoke's log watch (flow 5) reads it at
# run time when SUPABASE_ACCESS_TOKEN is not set, and sends it only to api.supabase.com. It is never written to a file.
#   powershell -NoProfile -File tools/supabase_cli_token.ps1
$sig = @'
[DllImport("advapi32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
public static extern bool CredRead(string target, int type, int flags, out IntPtr cred);
[DllImport("advapi32.dll")]
public static extern void CredFree(IntPtr cred);
[StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
public struct CREDENTIAL {
  public int Flags; public int Type; public string TargetName; public string Comment; public long LastWritten;
  public int CredentialBlobSize; public IntPtr CredentialBlob; public int Persist; public int AttributeCount;
  public IntPtr Attributes; public string TargetAlias; public string UserName;
}
'@
Add-Type -MemberDefinition $sig -Namespace WhCred -Name Native
$p = [IntPtr]::Zero
if (-not [WhCred.Native]::CredRead('Supabase CLI:supabase', 1, 0, [ref]$p)) { exit 1 }
try {
  $c = [Runtime.InteropServices.Marshal]::PtrToStructure($p, [type][WhCred.Native+CREDENTIAL])
  $bytes = New-Object byte[] $c.CredentialBlobSize
  [Runtime.InteropServices.Marshal]::Copy($c.CredentialBlob, $bytes, 0, $c.CredentialBlobSize)
  $s = [Text.Encoding]::UTF8.GetString($bytes)
  # go-keyring stores long values base64 behind this prefix
  if ($s.StartsWith('go-keyring-base64:')) { $s = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($s.Substring(18))) }
  [Console]::Out.Write($s.Trim())
} finally { [WhCred.Native]::CredFree($p) }
