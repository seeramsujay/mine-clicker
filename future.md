# Minecraft Automation Engine (mine-clicker): Future Roadmap & Technical Evolution

mine-clicker is an ultra-low-overhead (<15MB RAM) out-of-process Minecraft automation engine featuring packet interception, priority-preemptive task scheduling, and hardware HID injection with human motor delay models. This document outlines future architectural advancements.

---

## 1. Network Sniffing & Kernel-Level BPF Interception

- **Zero-Latency eBPF Network Tap**:
  - Replace userland Quarry TCP proxy with an eBPF (Extended Berkeley Packet Filter) socket filter attached to `cgroup2` network sockets.
  - Sniff Minecraft protocol packets (`Set Container Slot`, `Player Position`) with zero TCP proxy overhead, completely eliminating connection latency and local port binding requirements.
- **TLS / Auth Handshake Transparency**:
  - Automatically handle Microsoft OAuth / Minecraft session token validations transparently without MITM certificates.

---

## 2. Advanced Input Evasion & Human Biometrics

- **Reinforcement Learning Mouse Trajectory Generator**:
  - Train a Wasserstein GAN on real human mouse-tracking datasets to synthesize 2D cursor trajectories with natural micro-tremor, overshoot, and variable deceleration curves.
  - Automatically evaluate synthetic input streams against the latest anti-cheat heuristics (GrimAC, Vulcan, Polar).

---

## 3. Autonomous State & Multi-Macro Coordination

- **Automated Inventory & Tool Restocker**:
  - Deep integration with Prismarine-Item schema to automatically open ender chests, craft replacement diamond/netherite tools, and sort automated mob farm outputs.
- **Dynamic Wayland Native Input Bridge**:
  - Implement direct Wayland protocol input injection for modern Linux compositors (Hyprland, Sway, GNOME Wayland).
