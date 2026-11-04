{
  lib,
  rustPlatform,
  src,
  version ? (
    let
      cargo = builtins.fromTOML (builtins.readFile (src + "/Cargo.toml"));
      workspace = cargo.workspace.package.version or null;
      package = cargo.package.version or null;
    in
    if workspace != null then
      workspace
    else if package != null then
      package
    else
      "0.0.0"
  ),
}:

rustPlatform.buildRustPackage {
  pname = "whitemagic";
  inherit version src;

  cargoLock.lockFile = src + "/Cargo.lock";

  # Only the `wm` CLI/server binary from the workspace.
  cargoBuildFlags = [
    "-p"
    "whitemagic"
    "--bin"
    "wm"
  ];

  # The upstream test suite is large and machine-sensitive (embedded model /
  # timing tests); flip to true for a deep check once the build is green.
  doCheck = false;

  meta = {
    description = "WhiteMagic MCP server and `wm` CLI — local-first memory and governance substrate";
    homepage = "https://github.com/lbailey94/whitemagic";
    license = lib.licenses.mit;
    mainProgram = "wm";
    platforms = lib.platforms.linux;
  };
}
