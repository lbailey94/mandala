{ config, pkgs, lib, ... }:

{
  boot.kernel.sysctl = {
    # Restrict kernel dmesg to root
    "kernel.dmesg_restrict" = 1;

    # Disable unprivileged BPF (side-channel hardening).
    # NOTE: the Lakshmi/Yama eBPF sprint needs privileged collectors
    # (CAP_BPF/CAP_SYS_ADMIN) — run them as root services, or flip this to 0
    # on a behavioral-prototyping machine.
    "kernel.unprivileged_bpf_disabled" = 1;

    # Hardened ptrace scope (Yama LSM is always-on in NixOS kernels)
    "kernel.yama.ptrace_scope" = 2;

    # Anti-spoofing
    "net.ipv4.conf.all.rp_filter" = 1;
    "net.ipv4.conf.default.rp_filter" = 1;
    "net.ipv4.icmp_echo_ignore_broadcasts" = 1;

    # LMDB mmap & vector retrieval tuning
    "vm.swappiness" = 10;
    "vm.vfs_cache_pressure" = 50;
  };
}
