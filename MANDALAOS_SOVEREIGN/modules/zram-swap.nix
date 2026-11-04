{ config, pkgs, lib, ... }:

{
  # ZRAM swap: compressed in-RAM swap — the Sovereign spec's lever for running
  # local models on 8–15 GB machines. 50% is aggressive; tune per workload.
  zramSwap = {
    enable = true;
    algorithm = "zstd";
    memoryPercent = 50;
  };
}
