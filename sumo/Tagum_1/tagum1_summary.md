# Tagum_1 Intersection Summary

This document outlines the SUMO network configuration and traffic light logic for the **Tagum_1** intersection. It serves as a quick reference guide for modifying traffic light phases, demand routing, and understanding the physical layout.

## 📍 Intersection Overview

The main controlled junction at the centre of this network is defined as follows:

- **Junction ID:** `J1`
- **Type:** `traffic_light`
- **Traffic Light Program ID:** `J1`
- **Total Controlled Links:** `18`

> [!NOTE] 
> The traffic light `state` string in `tagum1.net.xml` must always contain exactly **18 characters** (e.g., `"rrrrrrrrrrGGGGrrrr"`). Each character index (0 to 17) corresponds directly to one specific directional movement or crosswalk, as detailed below.

## 🚦 Link Index Mapping

The table below maps each character index in the `state` string to its physical movement through the intersection. 

### Vehicle Movements

| Link Index | From Edge | To Edge | Approach Direction | Movement |
| :---: | :--- | :--- | :--- | :--- |
| **0** | `-E2` | `-E0` | North | Right Turn |
| **1** | `-E2` | `-E3` | North | Straight |
| **2** | `-E2` | `E1` | North | Left Turn |
| **3** | `-E1` | `E2` | East | Right Turn |
| **4** | `-E1` | `-E0` | East | Straight (Lane 1) |
| **5** | `-E1` | `-E0` | East | Straight (Lane 2) |
| **6** | `-E1` | `-E3` | East | Left Turn |
| **7** | `E3` | `E1` | South | Right Turn |
| **8** | `E3` | `E2` | South | Straight |
| **9** | `E3` | `-E0` | South | Left Turn |
| **10** | `E0` | `-E3` | West | Right Turn |
| **11** | `E0` | `E1` | West | Straight (Lane 1) |
| **12** | `E0` | `E1` | West | Straight (Lane 2) |
| **13** | `E0` | `E2` | West | Left Turn |

### Pedestrian Crosswalks

| Link Index | Crosswalk ID | Location | Crossing Edges |
| :---: | :--- | :--- | :--- |
| **14** | `J1_c0` | North | `E2` / `-E2` |
| **15** | `J1_c1` | East | `E1` / `-E1` |
| **16** | `J1_c2` | South | `-E3` / `E3` |
| **17** | `J1_c3` | West | `-E0` / `E0` |

---

## 🛠 How to Modify Traffic Lights
When editing `tagum1.net.xml` to create new `<phase>` definitions, match the index to the action you want:
- Use `G` for green (priority)
- Use `g` for green (yield to priority vehicles)
- Use `y` for yellow
- Use `r` for red

**Example Phase String (`rrrrrrrrrrGGGGrrrr`):**
Looking at the 18 characters, indices 10, 11, 12, and 13 are `G`. According to the table above, this allows the **West** approach to move right, straight (both lanes), and left, while all other movements (including pedestrians) are held on red (`r`).
