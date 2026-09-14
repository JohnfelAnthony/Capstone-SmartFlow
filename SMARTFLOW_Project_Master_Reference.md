# SMARTFLOW Project Master Reference

## Overview

SMARTFLOW is a local, simulation-based traffic analysis and decision-support system designed around a selected high-volume intersection and nearby road segments in Tagum City, Davao del Norte.[cite:1] Its main purpose is to simulate how vehicles, pedestrians, and traffic signals behave under both normal and disrupted conditions, then evaluate whether an adaptive reinforcement learning controller can outperform a fixed-time signal strategy.[cite:1]

The project is not a live deployment system for real-world signal hardware, CCTV feeds, roadside sensors, or government traffic operations.[cite:1] Instead, it is a research and experimentation platform that lets authorized users configure scenarios, run simulations, observe traffic behavior, compare control approaches, and review saved performance results in a local dashboard environment.[cite:1]

## Project Purpose

The central goal of SMARTFLOW is to build an AI-driven, agent-based traffic simulation and decision-support platform that models autonomous vehicle and pedestrian behavior while using reinforcement learning to optimize signal timing under varying traffic and road-constraint conditions.[cite:1] In practical terms, the project is meant to answer a simple but important question: if a realistic local intersection in Tagum City experiences congestion, pedestrian surges, emergencies, or disruptions such as lane closures or flooding, can adaptive signal control improve traffic flow better than a fixed schedule?[cite:1]

The project also serves as a capstone-scale integration system.[cite:1] It combines simulation, AI, local authentication, database-backed experiment management, dashboard monitoring, and browser-based visualization into one bounded research platform that is realistic enough to demonstrate technical depth but still feasible to complete in an academic setting.[cite:1]

## Core Concept

SMARTFLOW is built around three connected layers: a traffic simulation world, a traffic signal control layer, and a decision-support layer.[cite:1] SUMO acts as the microscopic traffic simulator, Python and TraCI handle runtime communication and control, the RL model selects signal actions, and the dashboard allows users to configure and observe experiments.[cite:1]

A key design principle is that the RL agent does not control individual vehicles or pedestrians directly.[cite:1] SUMO generates and updates the traffic environment, while Python reads state variables such as queue length, waiting time, pedestrian demand, emergency presence, and disruption conditions, then applies signal decisions back into the simulation loop.[cite:1]

## Problem Being Addressed

SMARTFLOW targets congestion and inefficiency caused not only by fixed-time signal control but also by localized constraints that often affect real intersections.[cite:1] These include lane closures, road construction, accidents, temporary blockages, localized flooding, heavy pedestrian demand, and emergency vehicle conditions.[cite:1]

This makes the project more realistic than a simple traffic-light optimization demo.[cite:1] The system is designed to test how signal behavior should adapt when traffic conditions become irregular, unpredictable, or interrupted by events that reduce capacity or change movement patterns.[cite:1]

## Study Context

The study site is intended to be one selected high-volume signalized intersection and its adjacent road segments in Tagum City.[cite:1] The selected area should include meaningful congestion behavior, pedestrian crossings, and enough movement complexity to support both baseline signal modeling and disruption-based evaluation.[cite:1]

The network is expected to be reconstructed using field observations, visual references, and SUMO tools such as `netconvert` and `netedit`.[cite:1] That preparation includes defining lanes, crossings, sidewalks, routes, and traffic light logic before the simulation is used for experiments.[cite:1]

## Main Objectives

The general objective is to develop SMARTFLOW as an AI-driven agent-based traffic simulation and decision-support system that models autonomous vehicles and pedestrians and uses reinforcement learning for adaptive signal optimization.[cite:1] The project document further breaks this into a set of specific objectives focused on network realism, dynamic demand generation, heterogeneous agents, adaptive control, scenario simulation, dashboard support, and fixed-time-versus-RL comparison.[cite:1]

### Specific objectives

- Design a realistic localized traffic simulation based on a selected Tagum City intersection and adjacent road segments.[cite:1]
- Simulate vehicles and pedestrians as autonomous agents with heterogeneous behaviors.[cite:1]
- Implement configurable traffic demand and scenario-based generation instead of relying only on static predefined inputs.[cite:1]
- Develop an RL-based signal controller that adapts to real-time traffic state.[cite:1]
- Evaluate normal and disrupted scenarios including heavy demand, pedestrian surges, emergencies, lane closures, construction, accidents, flooding, and blockages.[cite:1]
- Provide a local dashboard for login, configuration, control, monitoring, and evaluation.[cite:1]
- Compare RL control against a fixed-time baseline using measurable performance metrics.[cite:1]

## What Makes It Agent-Based

SMARTFLOW is agent-based because the simulated road users are represented as autonomous entities that move according to rules, profiles, and local conditions instead of being manually animated by the user.[cite:1] This gives the simulation more behavioral variety and makes it possible to test how different road-user types influence signal performance and congestion dynamics.[cite:1]

Vehicle agents may include normal, aggressive, cautious, delayed-reacting, and emergency drivers, each with different speed, following, acceleration, impatience, and lane-changing characteristics.[cite:1] Pedestrian agents may include compliant, slow, non-compliant, and crossing-heavy groups with different walking speeds, crossing compliance, and delay tolerance.[cite:1]

## Reinforcement Learning Role

The RL component is responsible only for traffic signal control, not for vehicle or pedestrian generation.[cite:1] Its job is to observe the state of the intersection and decide the next signal phase or timing action in a way that improves traffic performance while considering pedestrians, emergencies, and disruption conditions.[cite:1]

The document proposes an observation space that may include the current signal phase, queue lengths, waiting times, approaching vehicles, waiting pedestrians, pedestrians currently crossing, emergency presence, and active road-constraint conditions.[cite:1] The proposed action space may include North-South green, East-West green, protected turns when supported by geometry, pedestrian-priority phases, phase extension, and disruption-aware adaptive adjustments.[cite:1]

A practical reward function should penalize congestion and delay while rewarding throughput and better service for pedestrians and emergency vehicles.[cite:1] For a capstone-scale implementation, DQN or Double DQN is identified as a suitable and explainable RL approach.[cite:1]

## System Architecture

The documented architecture contains six major layers that work together during each simulation run.[cite:1]

### 1. Authentication and user access layer

This layer manages local login credentials, roles, and access to dashboard features and stored experiment records.[cite:1] It ensures that only authorized users can configure scenarios, start runs, and review saved outputs.[cite:1]

### 2. Scenario and constraint layer

This layer stores and applies demand levels, pedestrian activity, emergency conditions, lane closures, construction, accidents, flooding, temporary blockages, and similar disruptions before or during experiments.[cite:1]

### 3. SUMO simulation environment layer

This is the core traffic world where vehicles, pedestrians, routes, lanes, crossings, and traffic lights are simulated across the selected intersection and adjacent road segments.[cite:1]

### 4. Python and TraCI control layer

This layer launches SUMO, steps through the simulation, reads traffic state, converts that state into observation features, applies traffic light actions, computes metrics, and coordinates communication across the system.[cite:1]

### 5. Reinforcement learning decision engine

This layer receives the current traffic state and outputs the next signal decision using the chosen RL algorithm.[cite:1]

### 6. Dash and Three.js user interface layer

This layer provides the user-facing dashboard for authentication, scenario setup, controls, charts, reports, and live browser-based traffic visualization.[cite:1]

## End-to-End System Flow

SMARTFLOW is designed to follow a clear operational flow from login to experiment evaluation.[cite:1]

### User flow

1. An authorized user opens the local dashboard and logs in.[cite:1]
2. The user selects a scenario and activates any road constraints needed for the experiment.[cite:1]
3. The dashboard loads parameters from SQLite and local configuration records.[cite:1]
4. The user starts the simulation.[cite:1]
5. Python launches SUMO with the selected network, routes, signals, and scenario settings.[cite:1]
6. Vehicles and pedestrians are generated according to the chosen demand and behavior settings.[cite:1]
7. The RL controller reads state and issues signal actions during runtime.[cite:1]
8. The dashboard updates metrics, charts, and the live visualization continuously.[cite:1]
9. The user can pause, stop, or reset the experiment.[cite:1]
10. Results, metrics, and RL outputs are saved locally for analysis.[cite:1]

### Backend flow

1. Validate the active session and selected configuration.[cite:1]
2. Start SUMO through TraCI.[cite:1]
3. Read traffic conditions at each step and convert them into RL observations.[cite:1]
4. Pass the observation to the policy and receive the next signal action.[cite:1]
5. Apply the action in SUMO through TraCI.[cite:1]
6. Stream updated state to the dashboard and visualization layer.[cite:1]
7. Compute reward and log metrics to SQLite and local output files.[cite:1]
8. Continue until the simulation ends.[cite:1]

### Training flow

1. Load a training scenario set including disruption cases.[cite:1]
2. Reset the environment for each episode.[cite:1]
3. Store transitions and update the model through replay-based training.[cite:1]
4. Save checkpoints and outputs locally.[cite:1]
5. Evaluate the trained model on unseen normal and constrained variations.[cite:1]

## Technology Stack

The project document defines a focused local technology stack intended for research use rather than cloud deployment.[cite:1]

| Layer | Technology | Role in SMARTFLOW |
|---|---|---|
| Traffic simulation | SUMO | Simulates vehicles, pedestrians, routes, traffic lights, and localized road behavior.[cite:1] |
| Runtime control | TraCI | Connects Python to SUMO so the program can read state and change signals during simulation.[cite:1] |
| Backend logic | Python | Handles orchestration, metrics, authentication flow, and experiment workflows.[cite:1] |
| RL implementation | PyTorch or similar | Trains and runs the adaptive traffic signal controller.[cite:1] |
| Dashboard frontend | Dash | Provides the local dashboard for login, controls, monitoring, and charts.[cite:1] |
| Visualization | Three.js | Renders browser-based traffic visualization embedded in the dashboard.[cite:1] |
| Data storage | SQLite | Stores users, roles, scenarios, constraints, runs, metrics, and reports locally.[cite:1] |
| Map/network preparation | SUMO tools (`netconvert`, `netedit`) | Reconstructs the selected intersection and nearby segments from field data and references.[cite:1] |

## Database and Local Storage

SMARTFLOW uses SQLite as the main structured data layer rather than depending only on loose files.[cite:1] This allows the system to organize authentication, scenarios, run history, metrics, and summarized outputs on the local machine in a consistent way.[cite:1]

According to the project document, SQLite is expected to store user accounts and roles, traffic scenarios, road constraints, signal control mode selections, simulation run metadata, traffic metrics, RL outputs, and performance summaries.[cite:1] Local files are still needed for SUMO network files, route definitions, RL checkpoints, exported charts, and report documents.[cite:1]

## Authentication and Access Control

The system includes local authentication and access control because simulation configurations, experiment history, and results should only be available to approved users such as researchers, project members, or authorized evaluators.[cite:1] This design is intentionally lightweight and local, which fits an academic or office environment without requiring cloud identity services.[cite:1]

The current dashboard direction also reflects that local-application model through a branded control-center interface built in Dash.[cite:2] The project document states that user credentials and role information are stored in SQLite and that the dashboard should require successful login before exposing control and reporting features.[cite:1]

## Dashboard and User Interface

The current UI prototype is a dark-mode SMARTFLOW dashboard implemented in Dash with a premium control-center style.[cite:2] It already includes a branded top header, sidebar navigation, system-status indicators, a simulation view area, metrics cards, charts, scenario settings, event logs, RL status panels, and simulation control buttons.[cite:2]

The dashboard currently presents scenarios such as Tagum City intersections, a highway corridor, a school zone, and a custom four-way layout through a scenario dropdown, while also exposing controls for traffic density, pedestrian density, emergency vehicles, and weather conditions.[cite:2] The interface includes controls to start, pause, stop, and reset simulations, which aligns closely with the documented user flow in the project plan.[cite:1][cite:2]

### Current UI capabilities seen in the prototype

- Branded SMARTFLOW header with scenario selection and simulation timer.[cite:2]
- Sidebar modules for Dashboard, Simulation Control, Scenarios, Traffic Overview, Performance Metrics, AI Agent RL, Reports, Settings, and Help.[cite:2]
- KPI cards for waiting time, queue length, throughput, pedestrian counts, and emergency status.[cite:2]
- Trend charts for traffic flow and waiting time, currently populated with mock/randomized data in the present UI state.[cite:2]
- Recent-events panel for signal changes, congestion warnings, pedestrian actions, and emergency events.[cite:2]
- RL status panel showing agent details, training status, reward values, loss, and last action, also currently mock-driven in the present UI shell.[cite:2]
- Scenario settings for density, emergency presence, and weather, plus simulation control buttons.[cite:2]

## Visualization Layer

The project vision includes a browser-based visualization panel embedded in Dash and powered by Three.js.[cite:1] At the current UI stage, the prototype already expresses that visual direction through a stylized intersection scene containing roads, lane markings, sidewalks, crosswalks, traffic lights, vehicles, pedestrians, overlays, and animated dashboard elements.[cite:2][cite:3]

The stylesheet reinforces a strong visual identity for SMARTFLOW through a premium dark theme with structured color tokens, green accent highlights, compact controls, panel/card surfaces, and a traffic-scene inspired visual language.[cite:3] It also includes styling for intersection geometry, traffic lights, crosswalks, vehicles, emergency lights, pedestrians, overlays, KPI cards, control buttons, and status indicators, showing that visualization is a core user-facing part of the project rather than an optional add-on.[cite:3]

## Scenarios and Constraints

SMARTFLOW is meant to support both normal traffic conditions and disruption-driven scenario testing.[cite:1] This includes varying traffic density, pedestrian-heavy demand, emergency vehicle conditions, lane closures, road construction, accidents, temporary blockages, and localized flooding.[cite:1]

These scenarios matter because the project is not trying to optimize one fixed idealized signal cycle.[cite:1] It is trying to evaluate whether adaptive control remains effective when the local intersection experiences changing demand and reduced roadway capacity.[cite:1]

## Metrics and Evaluation

The project is designed to compare a fixed-time baseline against an RL-based controller under the same conditions.[cite:1] The key evaluation metrics listed in the project document include average vehicle waiting time, average queue length, maximum queue length, throughput, average pedestrian delay, emergency vehicle clearance time, signal phase efficiency, and congestion severity under road constraints.[cite:1]

The recommended experimental procedure is to run both fixed-time and RL control across the same scenarios multiple times, keep duration and demand settings comparable, log the outputs to SQLite and local export files, and compare the averaged results.[cite:1] The expected finding is that the adaptive controller should reduce waiting time and queue length, improve pedestrian service, and reduce emergency delay in most tested scenarios.[cite:1]

## Scope

The formal scope of SMARTFLOW covers one selected signalized intersection and its adjacent road segments in Tagum City, an agent-based simulation of vehicles and pedestrians, RL-based traffic signal control, multiple traffic and disruption scenarios, a Dash-based local dashboard, an embedded Three.js visualization panel, local SQLite-based storage, and comparative evaluation against a fixed-time controller.[cite:1]

This scope is intentionally focused.[cite:1] It limits the research to a manageable but meaningful localized environment rather than expanding into city-wide optimization or direct deployment infrastructure.[cite:1]

## Limitations

The project explicitly does not include deployment to physical traffic controllers, integration with government traffic centers, IoT hardware, CCTV analytics, live traffic sensors, or a city-wide traffic optimization model.[cite:1] It also does not claim full representation of every real-world factor, including simplified environmental effects and disruption approximations based on simulation rather than live operational data.[cite:1]

These limitations are important because they define SMARTFLOW as a research-grade decision-support tool rather than an operational smart-city traffic platform.[cite:1] The value of the project comes from controlled experimentation, comparative evaluation, and scenario testing, not from direct real-time traffic management.[cite:1]

## Why This Fits a Capstone

SMARTFLOW is strong as a capstone because it demonstrates integration across simulation, AI, database design, authentication, visualization, and dashboard engineering in one coherent system.[cite:1] At the same time, it remains bounded by focusing on one localized site, local deployment, and a limited but meaningful set of scenarios and metrics.[cite:1]

That balance makes the project academically defensible.[cite:1] It is technically rich enough to show originality and systems thinking, but it avoids overreaching into cloud services, live sensor networks, or city-scale infrastructure that would be difficult to finish within a capstone timeline.[cite:1]

## Current Implementation Direction

Based on the provided files, the current implementation direction already has a substantial dashboard UI shell in place, built in Dash with a detailed styling system and a simulated intersection display.[cite:2][cite:3] The present interface still uses mock values and randomized chart data in parts of the UI, which suggests that the frontend structure is ahead of the live simulation, database integration, and final control logic.[cite:2]

This is a reasonable development order for the project.[cite:2] It means SMARTFLOW already has a clear user-facing design language and operational dashboard structure that can later be connected to SQLite-backed authentication, SUMO/TraCI runtime data, real scenario configuration, and eventual RL outputs.[cite:1][cite:2]

## Recommended Mental Model for Other AI Tools

When another AI system is asked to help with SMARTFLOW, it should treat the project as a **localized traffic simulation and decision-support platform**, not just an RL experiment.[cite:1] The traffic simulator, the scenario system, the dashboard, the database, and the evaluation workflow are all essential parts of the project, not secondary accessories.[cite:1]

It should also understand that SMARTFLOW is **not** a live traffic-control deployment, a city-wide digital twin, or a hardware-integrated smart-city system.[cite:1] The most accurate framing is: a local research platform that reconstructs one Tagum City intersection, simulates vehicles and pedestrians in SUMO, applies fixed-time and RL-based traffic signal control, and lets authorized users analyze the resulting performance through a dashboard.[cite:1][cite:2]

## One-Paragraph Master Description

SMARTFLOW is a local AI-driven, agent-based traffic simulation and decision-support system for a selected high-volume intersection in Tagum City, Davao del Norte.[cite:1] It uses SUMO to simulate vehicles, pedestrians, routes, crossings, and traffic lights; Python and TraCI to control simulation runtime and collect state data; a reinforcement learning controller to adapt signal timing; SQLite to store users, scenarios, constraints, runs, and metrics; and a Dash-based dashboard with embedded visualization to let authorized users configure scenarios, monitor simulations, compare fixed-time and adaptive control, and review experiment results.[cite:1][cite:2]

## Short Reference Summary

| Topic | SMARTFLOW definition |
|---|---|
| What it is | A local traffic simulation and decision-support platform focused on one selected intersection in Tagum City.[cite:1] |
| Main simulator | SUMO.[cite:1] |
| Control bridge | Python + TraCI.[cite:1] |
| Adaptive intelligence | RL-based traffic signal controller, likely DQN or Double DQN.[cite:1] |
| Interface | Dash dashboard with browser-based visualization direction using Three.js.[cite:1][cite:2] |
| Data layer | SQLite for users, scenarios, constraints, runs, metrics, and reports.[cite:1] |
| Main users | Researchers, project members, and authorized evaluators.[cite:1] |
| Main comparison | Fixed-time traffic signal control versus RL-based adaptive control.[cite:1] |
| Main scenarios | Normal traffic, heavy traffic, pedestrian surges, emergency cases, lane closures, construction, accidents, flooding, and temporary blockages.[cite:1] |
| Main outputs | Simulation runs, metrics, adaptive policies, charts, reports, and comparative results.[cite:1] |
| Not included | Live deployment, CCTV, IoT sensors, government integration, and city-wide optimization.[cite:1] |

## Final Takeaway

SMARTFLOW should be understood as a complete research system whose value comes from the combination of localized traffic modeling, adaptive signal control, scenario testing, and decision-support presentation.[cite:1] Its real contribution is not only the RL model, but the full workflow that turns a reconstructed Tagum intersection into a configurable experimental environment where traffic behavior can be studied, compared, and explained through a structured local dashboard.[cite:1][cite:2][cite:3]
