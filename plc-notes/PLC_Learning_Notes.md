# PLC Learning Notes

**Muhammad Shaheer Riaz**
MSc Electrical and Electronics Engineering, Anglia Ruskin University

**Course:** Introduction to PLC and Industrial Automation (Zahraa Khalil, LinkedIn Learning)
**Path:** Become a PLC Developer
**Target platform:** Siemens TIA Portal

---

## Contents

**Part 1. The Big Picture**
1. [Automation System Levels](#1-automation-system-levels)
2. [Management Level](#2-management-level)

**Part 2. The Controller**

3. [PLCs and Distributed Control Systems](#3-plcs-and-distributed-control-systems)
4. [PLC Components](#4-plc-components)
5. [CPU Operation Modes](#5-cpu-operation-modes)
6. [I/O System in Detail](#6-io-system-in-detail)

**Part 3. Communication**

7. [Industrial Communication Protocols](#7-industrial-communication-protocols)
8. [OPC, Open Platform Communications](#8-opc-open-platform-communications)

**Part 4. Putting It Together**

9. [The Basic SCADA Architecture](#9-the-basic-scada-architecture)

**Part 5. Ladder Logic Programming**

10. [Ladder Logic Input Instructions](#10-ladder-logic-input-instructions)
11. [Ladder Logic Output Instructions](#11-ladder-logic-output-instructions)
12. [Worked Examples: Seal-In in Practice](#12-worked-examples-seal-in-in-practice)

**Appendix**

- [MCQ Revision Bank](#appendix-a-mcq-revision-bank)
- [Interview Quick Reference](#appendix-b-interview-quick-reference)
- [Interview Questions and Model Answers](#appendix-c-interview-questions-and-model-answers)

---
---

# Part 1. The Big Picture

---

## 1. Automation System Levels

The three levels of an automation system, bottom to top.

### Device level (bottom) = the field
- Sensors, transmitters, switches
- Flow, pressure, level, temperature instruments
- Valves, motors, actuators
- Physically out in the plant, touching the process

### Control level (middle) = the brain
- The PLC or DCS controller itself
- Reads inputs, runs the ladder logic, writes outputs
- Lives in the control room or rack room

### Application / Management level (top) = the screens
- SCADA, HMI, engineering workstation
- Your laptop sits here
- Operators monitor, log data, change setpoints. No direct control of field devices

### Signal direction
- **Up = inputs.** Raw signals travel device to control to SCADA
- **Down = outputs.** Commands travel SCADA to control to device

### Where marshalling cabinets fit
- Not a level of their own
- They are the wiring interface between device and control
- Field cables land there, get organised, then run to the PLC or DCS I/O cards

### Mapped to my Fauji Fertilizer experience
| What I did | Level |
|---|---|
| Calibrating flow and pressure transmitters | Device level |
| Loop checking wiring through marshalling cabinets | Device to control interface |
| Programming Triconex logic | Control level |
| Anything on an operator screen | Application level |

### One line to remember
> Field instruments sense it, the PLC decides it, SCADA shows it.

---

## 2. Management Level

**Slide definition:** Acquiring data from remote devices and providing overall control remotely from a host software platform.

### Breaking the definition down
| Phrase | What it actually means |
|---|---|
| Acquiring data | Pulling live values up from PLCs and field instruments |
| Remote devices | PLCs, RTUs and instruments spread across the plant or across sites |
| Overall control | Supervisory control. Changing setpoints, starting and stopping equipment |
| Remotely | From a control room, or over a network from another location entirely |
| Host software platform | SCADA, HMI or a historian running on a server or workstation |

### What lives at this level
- **SCADA** (Supervisory Control and Data Acquisition)
- **HMI** panels and operator screens
- **Historian** databases for long term trending
- **MES** (Manufacturing Execution System) in larger plants
- Engineering workstations, including my laptop running TIA Portal

### What it does day to day
- Displays live process values on mimic screens
- Raises and logs alarms
- Trends and archives data for analysis and reporting
- Lets operators change setpoints and issue start and stop commands
- Generates production and compliance reports

### Critical distinction to get right
The management level is **supervisory**, not direct.

It does **not** switch a motor on itself. It sends a request down to the PLC, and the **PLC** executes the actual control. The PLC keeps running its logic even if SCADA goes offline.

This matters for safety. Direct and safety critical control always stays at the control level, never at the management level.

### Real world example, fertilizer plant
1. A pressure transmitter reads 8.2 bar (**device level**)
2. The PLC or DCS compares it against setpoint and adjusts a control valve (**control level**)
3. SCADA displays the trend, logs it, and alarms if it exceeds limits. The operator can change the setpoint from the screen (**management level**)

### Why this level matters for my career
This is where my Python and machine learning work connects. Predictive maintenance, condition monitoring and analytics all run on data acquired at the management level. My MSc dissertation on ANN and LSTM models for battery health is exactly this kind of work applied to historian data.

Combining control level programming with management level data skills is a genuinely rare and valuable combination.

---
---

# Part 2. The Controller

---

## 3. PLCs and Distributed Control Systems

**Slide definition:** Send, receive, and process data from sensors as part of the control system.

### What they do, in order
1. **Receive** input signals from field sensors and instruments
2. **Process** those signals against the programmed logic
3. **Send** output commands back to valves, motors and actuators

Both PLC and DCS sit at the **control level** of the automation hierarchy.

### PLC vs DCS, the practical difference

| | PLC | DCS |
|---|---|---|
| Full name | Programmable Logic Controller | Distributed Control System |
| Best at | Fast, discrete, machine control | Continuous process control |
| Scope | One machine or one area | Whole plant, many control loops |
| Architecture | Standalone controller | Controllers distributed across the plant, centrally managed |
| Typical use | Packaging line, conveyor, motor control | Refinery, fertilizer plant, chemical process |
| Response | Very fast scan times | Optimised for stability and loop control |
| Example products | Siemens S7-1200, Allen-Bradley ControlLogix | Siemens PCS 7, Honeywell Experion, Yokogawa Centum |

### Key point
The line between them is blurring. Modern PLCs handle process control, and modern DCS platforms use PLC style logic. **Learning PLC fundamentals transfers to DCS work.**

### Relevant to me
Fauji Fertilizer ran DCS and ESD, which is the classic process industry setup. The ladder and function block logic I write for a PLC is the same thinking used in DCS configuration.

### Interview angle
If asked "do you know DCS or PLC", the strong answer is that I have hands on DCS and ESD exposure from a live plant turnaround, and I am now building formal PLC programming skills on Siemens. That covers both sides of the control level.

---

## 4. PLC Components

Every PLC, regardless of vendor, is built from the same four building blocks.

| Component | Role in one line |
|---|---|
| **Power supply** | Feeds clean DC power to the CPU and modules |
| **Controller CPU** | The brain. Runs the program |
| **I/O system** | The senses and hands. Connects to the real world |
| **Software** | Where the program is written and downloaded from |

### Power supply
- Converts incoming mains AC, typically 230 V AC in the UK, down to low voltage DC
- **24 V DC is the industrial standard** for control circuits and most field devices
- Must be correctly sized for the CPU plus every module plus connected field devices
- Often backed by a UPS or battery so the controller survives a brief supply dip
- A weak or undersized supply causes intermittent faults that are notoriously hard to diagnose

### Controller CPU
- The processing unit that executes your program
- Contains the **memory**, both program memory and data memory
- Runs continuously in a loop called the **scan cycle**
- Has a mode switch, usually RUN, STOP and MRES or reset
- Status LEDs for run, stop, error and forcing, the first thing to check when troubleshooting

**The scan cycle, the single most important concept in PLC programming**

The CPU repeats these steps thousands of times per second:

1. **Read inputs.** Take a snapshot of every input and store it in the input image table
2. **Execute program.** Run the logic top to bottom, left to right, using that snapshot
3. **Write outputs.** Update the physical outputs from the output image table
4. **Housekeeping.** Diagnostics, communications, then repeat

**Why this matters in practice**
- The program does **not** see an input change mid scan. It works from the snapshot taken at the start
- Output coils do not energise the instant the rung is solved. They update at the end of the scan
- This is the root cause of many beginner bugs, including one scan delays and unexpected rung ordering behaviour
- **Scan time** is how long one full cycle takes, typically a few milliseconds. A long or inconsistent scan time is a warning sign

### I/O system
The interface between the PLC and the physical plant. Four fundamental types:

| Type | Abbreviation | Signal | Example device |
|---|---|---|---|
| Digital input | DI | On or off, 24 V DC | Push button, limit switch, proximity sensor |
| Digital output | DO | On or off | Relay, contactor, indicator lamp, solenoid valve |
| Analogue input | AI | Continuous, 4 to 20 mA or 0 to 10 V | Pressure, flow, level, temperature transmitter |
| Analogue output | AO | Continuous, 4 to 20 mA or 0 to 10 V | Control valve positioner, variable speed drive setpoint |

**Points worth knowing**
- **4 to 20 mA is the process industry standard.** The reason it starts at 4 mA rather than 0 is live zero. If the signal reads 0 mA, you know the loop is broken rather than the process genuinely reading zero. That is a built in fault detection feature
- **Specialty modules** also exist: high speed counters, motion and positioning, PID, thermocouple and RTD, and communication modules
- **Local vs remote I/O.** Local sits in the same rack as the CPU. Remote I/O sits out in the plant and connects back over PROFINET or PROFIBUS, which saves enormous amounts of cabling
- **Safety I/O** is a separate, certified category used for emergency stops and safety interlocks, for example Siemens Safety Integrated or Triconex

### Software
Two distinct meanings, do not confuse them:

1. **The programming environment**, the tool on the engineer's laptop
   - Siemens: **TIA Portal**
   - Allen-Bradley: Studio 5000
   - Beckhoff: TwinCAT
   - Vendor neutral: CODESYS

2. **The program itself**, the logic downloaded into the CPU
   - Written in one of the **IEC 61131-3** languages
   - Ladder Diagram (LD), Function Block Diagram (FBD), Structured Text (ST), Sequential Function Chart (SFC), Instruction List (IL)

**What the software also does beyond writing logic**
- Hardware configuration, telling the CPU which modules are fitted and where
- Tag and symbol management
- Online monitoring and forcing, watching live values while the program runs
- Diagnostics and fault reporting
- Uploading and downloading programs, and version backup

### Physical assembly
- Modules mount on a **rack** or **chassis**, usually DIN rail mounted in a control panel
- The **backplane** is the internal bus that carries power and data between modules
- Typical left to right order: power supply, CPU, then I/O and communication modules
- Everything sits inside a control panel, which is what marshalling cabinets ultimately wire into

### Relevant to me
My BSc final year project, the Arduino based PLC module, contained every one of these four components. A regulated power supply, the microcontroller acting as CPU, input and output circuitry driving stepper, servo and DC motors, and the software I wrote plus the HMI dashboard. That is a genuine talking point in interviews, because it shows I have built a controller from first principles rather than only configured one.

---

## 5. CPU Operation Modes

Every PLC CPU runs in one of two fundamental modes.

**Slide definitions**

| Mode | Slide wording |
|---|---|
| **Programming mode** | Download logic from software |
| **Run mode** | Execute and operate the program |

**Put another way**

| Mode | What the CPU is doing |
|---|---|
| **Programming mode** | Program is **not** executing. The CPU accepts a new program from the engineering software |
| **Run mode** | Program **is** executing. The scan cycle runs continuously and outputs are live |

### Programming mode
Also called **STOP** mode on most real hardware.

- Logic execution is **halted**
- Outputs are switched to a safe state, normally all de-energised
- Used to **download** a new or modified program into the CPU
- Used for hardware configuration changes, such as adding an I/O module
- The plant is not being controlled while in this mode

### Run mode
- The CPU continuously executes the scan cycle: read inputs, execute program, write outputs, repeat
- Outputs are **live** and physically driving field devices
- The engineer can still go **online** to monitor live values and trend the logic
- This is the normal operating state of any working plant

### What the vendors actually call these

| | Siemens | Allen-Bradley |
|---|---|---|
| Programming | STOP | PROG |
| Running | RUN | RUN |
| Memory reset | MRES | n/a |
| Software selectable | via TIA Portal | REM (remote), lets the software switch modes |

Allen-Bradley's **REM** position is worth knowing. It hands mode control to the software, so an engineer can switch between program and run remotely rather than physically turning a key on the CPU.

### The safety point that actually matters

Switching a CPU from RUN to STOP **stops controlling the plant**. Outputs drop out. On a live process this can trip equipment, spill product, or in the worst case create a hazardous condition.

Rules that follow from this:
- Never change CPU mode on a live plant without a permit, an agreed procedure and operator awareness
- Always confirm what state the outputs will fall to when the CPU stops
- Safety systems such as ESD are deliberately independent of the main PLC, precisely so that stopping one controller does not remove protection

### Downloading, the practical distinction

- **Full download** normally requires the CPU to be in STOP or programming mode
- **Online edit**, sometimes called run mode editing, lets small logic changes go in while the CPU stays in RUN. Supported by most modern platforms, but it must be done carefully because the change takes effect immediately on a live process

### Related concept, forcing
Forcing overrides an input or output to a value you choose, regardless of the real field signal. It is useful for commissioning and testing, for example proving a valve opens without waiting for the real process condition.

Forcing is also genuinely dangerous, since the program is no longer reacting to reality. Forces must always be documented and removed before handover. Most CPUs light a dedicated LED whenever any force is active.

### Relevant to me
During the Fauji Fertilizer turnaround, loop checking is exactly the activity that depends on these modes and on forcing. The plant was down, controllers were not running the process, and signals were driven and verified end to end from field instrument through marshalling cabinet to the I/O card.

---

## 6. I/O System in Detail

The I/O system is the interface between the PLC and the physical plant. Four types, split by signal nature and direction.

> **Note on the slide.** The title reads "I/O System Input" but the content is labelled Output. The course reuses the same title slide for both. The values shown, 0 to 10 V DC or 4 to 20 mA, apply to **analogue** signals in both directions.

### The four I/O types

| Type | Abbreviation | Signal nature | Example device |
|---|---|---|---|
| Digital input | DI | On or off | Push button, limit switch, proximity sensor |
| Digital output | DO | On or off | Relay, contactor, lamp, solenoid valve |
| Analogue input | AI | Continuous value | Pressure, flow, level, temperature transmitter |
| Analogue output | AO | Continuous value | Control valve positioner, VSD speed setpoint |

---

### Analogue signal values

Same two standard ranges for both input and output.

| Range | Notes |
|---|---|
| **4 to 20 mA** | Current loop. **The process industry standard** |
| **0 to 10 V DC** | Voltage. Common on machines and drives |

Other ranges exist but are less common: 0 to 20 mA, 1 to 5 V, and bipolar ranges such as -10 to +10 V for signals that need direction, for example a drive running forward and reverse.

**Why 4 to 20 mA beats 0 to 10 V**

| | 4 to 20 mA | 0 to 10 V |
|---|---|---|
| Noise immunity | Excellent, current is unaffected by induced noise | Poorer, picks up electrical noise |
| Cable length | Long runs, hundreds of metres | Short runs only |
| Voltage drop | Immune, current is constant along the loop | Signal degrades over distance |
| Fault detection | **Yes**, live zero | No, 0 V is ambiguous |

**Live zero, the key concept**

The signal starts at 4 mA, not 0 mA, on purpose.

- 4 mA = 0 percent of range
- 20 mA = 100 percent of range
- **0 mA = broken wire or dead instrument**

If it started at 0 mA there would be no way to distinguish a genuine zero reading from a failed loop. This is fault detection built into the signal standard itself.

**Scaling example.** A pressure transmitter ranged 0 to 10 bar:

| Current | Pressure |
|---|---|
| 4 mA | 0 bar |
| 8 mA | 2.5 bar |
| 12 mA | 5 bar |
| 20 mA | 10 bar |
| 0 mA | Fault, loop broken |

**Resolution.** Analogue modules convert between the real world signal and an integer the CPU can use. Typically 12, 14 or 16 bit. A 16 bit module gives 65536 steps across the range, which is far finer than any field instrument actually needs, so accuracy is normally limited by the instrument rather than the card.

---

### Digital signal values

This is the part the slide did not cover.

**Digital inputs, typical values**

| Voltage | Where used |
|---|---|
| **24 V DC** | **The industrial standard.** Most modern PLC inputs |
| 110 or 230 V AC | Older installations, or where field devices are mains powered |
| 5 V DC / TTL | Electronics and board level, rare on industrial PLCs |
| 48 V DC | Occasional, some legacy and rail applications |

**Digital outputs, typical values and module types**

| Output type | Typical rating | Behaviour |
|---|---|---|
| **Transistor** | **24 V DC**, roughly 0.5 to 2 A per channel | Fast switching, solid state, long life. DC only |
| **Relay** | 24 V DC or up to 230 V AC, roughly 2 A | Volt free contact, switches AC or DC, slower, mechanically wears out |
| **Triac** | 110 or 230 V AC | Solid state AC switching |

**How to choose**
- **Transistor** for fast, frequently switched DC loads, for example solenoid valves and pilot lights
- **Relay** when you need a **volt free or dry contact**, when switching AC, or when the load voltage differs from the PLC supply
- **Triac** for AC loads that switch often, where a relay would wear out

**Important limitation.** PLC outputs are low current. They do **not** drive a motor directly. The output energises a **contactor or relay coil**, and that contactor switches the motor's power circuit. The PLC handles control, not power.

---

### Sinking and sourcing

Trips up nearly every beginner, and it comes up in interviews.

| Term | Meaning |
|---|---|
| **Sourcing** | The device **supplies** positive current out. Corresponds to **PNP** sensors |
| **Sinking** | The device **receives** current in, providing the path to 0 V. Corresponds to **NPN** sensors |

The rule: **a sourcing device must pair with a sinking device.** A PNP sourcing sensor connects to a sinking input card, and vice versa. Get it backwards and the input simply never registers, with no obvious fault to see.

Regional habit worth knowing: **PNP sourcing is the norm in Europe**, NPN sinking is more common in Asia.

---

### Other points worth knowing

- **Isolation.** Good I/O modules are optically isolated, so a fault in the field cannot damage the CPU
- **Channel count.** Modules typically come in 8, 16 or 32 channels
- **Local vs remote I/O.** Local sits in the CPU rack. Remote I/O sits out in the plant and connects back over PROFINET or PROFIBUS, saving enormous amounts of cabling
- **Specialty modules.** High speed counters, motion and positioning, PID, thermocouple and RTD, weighing, and communication modules
- **Safety I/O.** A separate certified category for emergency stops and interlocks, for example Siemens Safety Integrated or Triconex
- **Intrinsically safe I/O.** Required in hazardous areas such as fertilizer, oil and gas. Limits energy into the field so it cannot ignite an explosive atmosphere

### Relevant to me
The transmitters I calibrated at Fauji Fertilizer, flow, pressure, level and temperature, were 4 to 20 mA analogue inputs. Loop checking is precisely the exercise of proving that signal path end to end, from the instrument through the marshalling cabinet to the correct channel on the analogue input card. Being able to explain live zero and why a 0 mA reading means a broken loop is a strong, specific answer in an interview.

---
---

# Part 3. Communication

---

## 7. Industrial Communication Protocols

Protocols are how the levels of the automation hierarchy actually talk to each other. Field instruments to controller, controller to controller, controller to SCADA.

### The main protocols at a glance

| Protocol | Vendor origin | Used for |
|---|---|---|
| **PROFINET** | Siemens | Modern Siemens standard. Ethernet based, real time. **Learn this one** |
| **PROFIBUS** | Siemens | Older Siemens fieldbus. Still very widely installed |
| **ControlNet** | Rockwell / Allen-Bradley | Real time, deterministic data transfer between devices on a network |
| **DeviceNet** | Rockwell / Allen-Bradley | Device level. Sensors and actuators |
| **EtherNet/IP** | Rockwell / ODVA | Modern Rockwell standard. Ethernet based |
| **Modbus** | Modicon, now open | Simple and universal. Extremely common, easy to learn |
| **HART** | Open standard | Digital signal layered on top of 4 to 20 mA wiring |
| **Foundation Fieldbus** | Open standard | Process industry. Common in oil, gas and chemical |
| **EtherCAT** | Beckhoff | Very high speed motion control. Used by Tesla and advanced manufacturing |
| **IEC 61850** | Open standard | Electrical substations and smart grids |
| **OPC UA** | Open standard | Vendor neutral data exchange, typically controller to SCADA or IT systems |

### HART, worth knowing properly

HART stands for **Highway Addressable Remote Transducer**.

The key idea is that HART is **two way, or bidirectional**. It sends and receives.

- It layers a **digital signal on top of the existing 4 to 20 mA analogue current loop**
- The analogue 4 to 20 mA still carries the primary process value
- The digital signal simultaneously carries configuration, diagnostics and secondary values
- This means **no new wiring is needed**. It works over the cabling already installed

**Why it matters:** an engineer can configure, calibrate and diagnose a field instrument remotely, without walking out to the device. It also reports device health, which feeds directly into predictive maintenance.

**Relevant to me:** the flow, pressure, level and temperature transmitters I calibrated at Fauji Fertilizer are exactly the class of device that uses HART.

### PROFIBUS, worth knowing properly

The defining feature is that PROFIBUS uses a **single cable** to connect many devices in series, rather than running individual wires from every device back to the controller.

- One shared bus cable, devices connected along it
- Massively reduces wiring, cable trays, marshalling terminations and installation cost
- Each device has its own address on the bus
- Compare with traditional wiring, where every single instrument needs its own dedicated pair back to the I/O card

**Two main variants**
- **PROFIBUS DP** (Decentralised Peripherals). Fast, for connecting remote I/O and drives
- **PROFIBUS PA** (Process Automation). For field instruments in process plants, including hazardous areas

**PROFIBUS vs PROFINET:** PROFIBUS is the older serial fieldbus. PROFINET is the modern Ethernet based successor. New Siemens projects use PROFINET, but PROFIBUS is still everywhere in installed plants, so both are worth knowing.

### What to prioritise given my Siemens path
1. **PROFINET** and **PROFIBUS**, non negotiable for Siemens work
2. **HART** and **Foundation Fieldbus**, directly relevant to my instrumentation background
3. **Modbus**, universal and quick to pick up
4. **OPC UA**, the bridge between control and my Python and data work
5. EtherNet/IP and ControlNet, only if I move toward Allen-Bradley

---

## 8. OPC, Open Platform Communications

**Slide definitions**
- A standard for a secure and reliable exchange of data
- Used in the applications that need access to data from any data source

That second line is the whole point. **Any data source.** OPC does not care whether the data comes from a Siemens PLC, an Allen-Bradley PLC, a temperature controller or a database. The client asks the same way every time.

### The problem OPC solves

A real plant contains PLCs from several vendors, each speaking its own protocol. Without a standard, every HMI, SCADA package and database would need a custom driver written for every controller it talks to. That is a combinatorial mess.

OPC is the **common language** that sits above all of them. Any controller can publish its data through OPC, and any application can read it, regardless of who made either one.

> OPC is vendor neutral. It is what lets a Siemens PLC, an Allen-Bradley PLC and an Omron PLC all feed the same SCADA screen.

### Where it sits in the architecture

From the slide diagram, reading bottom to top:

```
                    HMI                  top level supervision
                     |
    +--------+-------+--------+--------------+
   HMI      HMI            HMI           Database
    |        |               |               |
   OPC      OPC             OPC             OPC     <- the common layer
    |        |               |               |
   PLC      PLC             PLC             PLC     control level
```

Each PLC publishes through OPC. HMIs and databases consume from it. A higher level HMI can then aggregate several lower ones.

**The key idea:** OPC makes data from many different controllers available **in one place**, so applications like HMI, SCADA, historians and databases can all reach it consistently.

### Server and client, the parent and child model

OPC is implemented in **server and client pairs**.

| Role | Analogy from the slide | What it does |
|---|---|---|
| **OPC Server** | **Parent** | **Provides** the data. Sits close to the controller and exposes its tags |
| **OPC Client** | **Child** | **Requests and uses** the data. The HMI, SCADA, historian or database |

Server supplies, client consumes. One server can serve many clients at once, which is exactly why the model scales.

### The four connection scenarios

| Scenario | What it means |
|---|---|
| **Single connection** | One client talks to one server. The simplest case, one HMI reading one PLC |
| **Aggregation** | One client pulls from **multiple servers** at once, combining data from many controllers into a single view |
| **Tunnelling** | Data passed **across a network**, between sites or through a firewall, securely |
| **Bridging** | **Server to server** transfer, moving data directly between two systems without an application in the middle |

Aggregation is the one that matters most in practice. It is how a plant wide SCADA screen shows data from a dozen different PLCs at once.

**Memory hook:** Aggregate = gather many. Tunnel = go through. Bridge = span between two of the same thing.

### OPC middleware, Cogent DataHub

Named in the course, worth knowing as an example of the product category.

Cogent DataHub is middleware that sits in the middle of an OPC architecture. Its defining feature is that it acts as **both an OPC server and an OPC client at the same time**.

That dual role is what makes it useful. It can consume data as a client from one system and republish it as a server to another, which is exactly what aggregation, tunnelling and bridging all require. One product covers all four connection scenarios.

### OPC Classic vs OPC UA, worth knowing

| | OPC Classic (DA, HDA, A&E) | **OPC UA** (Unified Architecture) |
|---|---|---|
| Built on | Microsoft COM and DCOM | Platform independent |
| Platform | **Windows only** | Windows, Linux, embedded, cloud |
| Security | Weak, DCOM was notoriously awkward | **Built in encryption, authentication, certificates** |
| Data model | Simple tag values | Rich, structured, self describing |
| Status | Legacy, still widely installed | **The modern standard. Learn this one** |

**OPC UA is the important one.** It is the backbone of Industry 4.0 and the standard route for getting plant data into IT systems, databases and cloud analytics.

### Why this section matters more to me than most

This is the **exact bridge between my control skills and my Python and machine learning background**.

- A PLC controls the process
- **OPC UA exposes that process data**
- A Python client reads it, and my ANN or LSTM models consume it for predictive maintenance

The Python library `opcua` or `asyncua` connects to an OPC UA server in a few lines. That means I can build a genuine portfolio project: PLC logic in TIA Portal or CODESYS, data exposed over OPC UA, Python reading it live and running a model on it.

Very few graduate candidates can demonstrate that end to end chain. It directly combines the control level with the management level, which is the combination I identified as my differentiator.

**Action point:** once TIA Portal and CODESYS are set up, build a small OPC UA to Python demo and put it on GitHub.

---
---

# Part 4. Putting It Together

---

## 9. The Basic SCADA Architecture

This section is the capstone. It assembles everything from the earlier sections into one working system: field devices, PLCs, HMI, networks and remote sites.

**SCADA** stands for **Supervisory Control and Data Acquisition**. Both halves of the name matter. It **acquires data** from across the plant, and it provides **supervisory control**, meaning it requests actions rather than executing them directly.

### The architecture from the slide

```
   HMI ---- SCADA ------------ SCADA Master ----LAN---- Remote Location
              |                                              |
             PLC                                            PLC
              |                                              |
      +-------+-------+                                       |
      |       |       |                                  Field device
  Pushbutton Sensor  Control                             (transmitter)
                     Valve
```

### Walking the diagram, bottom to top

| Layer | What it is | Level |
|---|---|---|
| **Pushbutton, sensor, control valve** | Field devices. Two inputs and one output | Device |
| **PLC** | Reads the inputs, runs the logic, drives the valve | Control |
| **SCADA** | Local supervisory station. Displays, trends, alarms, logs | Management |
| **HMI** | Operator interface panel attached to the system | Management |
| **SCADA Master** | Central server that collects from multiple SCADA nodes and sites | Management |
| **LAN** | The network linking the master to remote locations | Communication |
| **Remote Location** | A second site with its own PLC and field devices | All three, replicated |

### The key structural points

**1. The PLC does the controlling, not SCADA.**
The pushbutton and sensor wire into the PLC, and the PLC drives the control valve. SCADA sits above and watches. If the SCADA station is switched off, the PLC keeps controlling the process. This is the single most important thing the diagram is teaching.

**2. SCADA Master is the hub, not just another screen.**
A local SCADA station covers one area. The **master** aggregates several stations and sites into one plant wide picture. This is where OPC aggregation from section 8 is actually used.

**3. The LAN is what makes it distributed.**
The whole point of SCADA is supervising equipment that is **geographically spread out**. The LAN, or a WAN over a wider area, carries data from remote locations back to the master.

**4. Remote locations mirror the same structure.**
The remote site has its own PLC and its own field devices. It runs independently and reports back. It does not depend on the master to keep operating, which is exactly the resilience you want.

### HMI vs SCADA, a distinction that gets confused

| | HMI | SCADA |
|---|---|---|
| Scope | One machine or one area | Whole plant, often multiple sites |
| Form | Usually a physical panel on or near the equipment | Software on a PC or server |
| Function | Local operation and status | Supervision, trending, alarming, logging, reporting |
| History | Little or none | Extensive, via a historian |
| Location | On the plant floor | Control room |

Simply put: **every SCADA system includes HMI functionality, but not every HMI is a SCADA system.**

### RTU vs PLC, worth knowing for SCADA work

Classic SCADA at remote sites often uses an **RTU**, a Remote Terminal Unit, rather than a PLC.

| | PLC | RTU |
|---|---|---|
| Strength | Fast, complex control logic | Wide area telemetry and data collection |
| Location | Usually on site, in a panel | Genuinely remote, for example a pipeline valve or a reservoir |
| Power | Mains | Often solar or battery, low power |
| Comms | Wired network | Radio, cellular, satellite |

Modern PLCs increasingly do both jobs, so the distinction is fading, but the term still appears in SCADA job adverts, especially in **water and utilities**, which is a big UK employer.

### Where SCADA is used
- Water and wastewater networks, treatment works spread across a region
- Electricity transmission and distribution, substations
- Oil and gas pipelines
- Large process plants, including fertilizer and chemical
- Building management across multiple sites

### Common SCADA products, useful names to recognise
- **Siemens WinCC**, which pairs with TIA Portal, the one relevant to my path
- Ignition by Inductive Automation, increasingly popular and named in Tesla job adverts
- Wonderware, now AVEVA
- Rockwell FactoryTalk View
- GE iFIX and Cimplicity

### Security note worth mentioning in an interview
Because SCADA connects a control network to wider networks and often the internet, it is a **cyber security concern**. Stuxnet targeted exactly this kind of system. Good practice is network segmentation, firewalls between the control network and the business network, and a demilitarised zone for data that IT systems need.

This is a genuinely current topic, and mentioning **OT security** shows awareness beyond the syllabus.

### Relevant to me
This diagram is essentially the architecture I worked inside at Fauji Fertilizer, with the DCS filling the SCADA and control role. The field devices I calibrated sit at the bottom, the marshalling cabinets are the wiring between the bottom two layers, and the Triconex ESD system runs alongside as an independent safety layer.

It is also where my data work attaches. The SCADA Master and its historian are the source of the plant data that predictive maintenance models consume.

---
---

# Part 5. Ladder Logic Programming

---

## 10. Ladder Logic Input Instructions

Input instructions are the **conditions** on a rung. They sit on the left and decide whether power can flow through to the output on the right.

There are two of them, and understanding the difference properly is the foundation of everything that follows.

### First, the vocabulary

The word "input" is used for two completely different things, and keeping them apart prevents most beginner confusion.

```
  Physical input devices          Inputs within PLC programming
            |                                  |
            v                                  v
  Field input devices                   Input instructions
       (contacts)                        (XIC and XIO)

  Real hardware in the plant       Symbols in your program
  A switch you can touch           An instruction reading a bit
```

**The two families of terms, side by side**

```
     Field device / relay                  Program instructions
      (the HARDWARE)                        (the SOFTWARE)
        /          \                          /          \
       v            v                        v            v
  +-----------+ +-------------+       +-------------+ +-------------+
  | Normally  | | Normally    |       | Examine if  | | Examine if  |
  |   open    | |   closed    |       |  open (XIO) | | closed (XIC)|
  |   (NO)    | |    (NC)     |       |             | |             |
  +-----------+ +-------------+       +-------------+ +-------------+

  Decided by wiring and the           Decided by you, when writing
  electrical drawing                  the program

  Describes the contact's             Describes which BIT VALUE
  resting physical state              makes the instruction true
```

**NO and NC belong to hardware. XIO and XIC belong to software.** Never use the pairs interchangeably, and never assume a field device's type dictates the instruction you write.

| | Field input device | Input instruction |
|---|---|---|
| What it is | Real hardware out in the plant | A symbol in the ladder program |
| Also called | Field contact | XIC or XIO |
| Examples | Push button, limit switch, proximity sensor, pressure switch | `----\| \|----` and `----\|/\|----` |
| Described as | Normally open or normally closed, by how it is **wired** | Examine if closed or examine if open, by which **bit value** makes it true |
| Where it lives | The device level | The program, inside the CPU |
| Can you touch it | Yes | No |

**Why this distinction is the whole point**

Both get called "normally open" and "normally closed" in casual conversation, which is exactly what causes the confusion.

- A **field device** is normally open or normally closed by its **physical construction and wiring**. That is a hardware fact, decided by the electrician and the drawing.
- An **input instruction** is XIC or XIO by which **bit value makes it true**. That is a software choice, decided by you when writing the program.

**They are chosen independently.** A normally closed stop button in the field is programmed with an XIC. Assuming the two must match is the single most common beginner error in ladder logic.

The signal path diagram later in this section shows exactly where the two worlds separate, at the point where the input module writes the bit into memory.

### The two symbols

```
    XIC                              XIO
  Examine if Closed              Examine if Open

  ----| |----                    ----|/|----

  True when the bit is 1         True when the bit is 0
  (ON  / energised)              (OFF / de-energised)
```

| | XIC | XIO |
|---|---|---|
| Full name | Examine if Closed | Examine if Open |
| Symbol | `----| |----` | `----|/|----` |
| Also called | Normally Open contact, NO | Normally Closed contact, NC |
| Passes power when the bit is | **1, ON, TRUE** | **0, OFF, FALSE** |
| Blocks power when the bit is | 0, OFF, FALSE | 1, ON, TRUE |
| Siemens name | Normally open contact | Normally closed contact |

The distinguishing mark is the **forward slash** through the XIO symbol. Slash means invert.

---

### Quick reference, the whole thing on one screen

**XIC, Examine if Closed** `----| |----`

```
   bit = 0                        bit = 1
  ----| |----                    ==| |==     <- power flows
    FALSE                          TRUE
```
> **XIC is TRUE when the bit is 1.**
> Think of it as a normal switch. Turn it on, power passes.

**XIO, Examine if Open** `----|/|----`

```
   bit = 0                        bit = 1
  ==|/|==   <- power flows       ----|/|----
    TRUE                           FALSE
```
> **XIO is TRUE when the bit is 0.**
> The slash inverts it. Turn the bit on and it blocks.

### The truth table

| Bit value | XIC `----| |----` | XIO `----|/|----` |
|:---:|:---:|:---:|
| **0** (OFF) | **FALSE**, blocks | **TRUE**, passes ✅ |
| **1** (ON) | **TRUE**, passes ✅ | **FALSE**, blocks |

**They are exact opposites.** For any given bit, one passes and the other blocks. Always.

### Three ways to remember it

1. **The slash means NOT.** XIC is "bit", XIO is "not bit"
2. **XIC matches intuition, XIO reverses it.** XIC on when on, XIO on when off
3. **The letter tells you the true state.** XI**C**losed wants the bit **C**losed, meaning 1. XI**O**pen wants the bit **O**pen, meaning 0

---

### How an input actually reaches the program

This is the signal path from the real world into a rung. It explains **why** the instructions behave the way they do.

```
   Input X          <- the physical device, a real switch or sensor
      |
      v
  PLC input module  <- converts the 24 V field signal into a logic bit
      |
      |  Store in memory
      v
  Input signal      <- the input image table. A snapshot of every input,
    memory             taken at the start of the scan
      |
      |  Read X0 status from memory
      v
      X0
  ----| |-------------------------------(  )----
   the contact reads the BIT,           output
   not the physical device
```

**Four stages, in order**

| Stage | What happens |
|---|---|
| 1. Physical device | A switch closes or a sensor triggers out in the plant |
| 2. PLC input module | Detects the 24 V signal, filters and isolates it, converts it to a 1 or 0 |
| 3. Input signal memory | The bit is stored in the **input image table**, one address per channel, for example X0 |
| 4. Ladder instruction | The contact in your program **reads that stored bit**, not the device itself |

### The two things this diagram is really teaching

**1. Your program never touches the field device.**
The contact labelled X0 is not the switch. It is an instruction that reads **address X0 in memory**. Several rungs can examine the same X0, and each one reads the same stored bit. That is why you can use one physical input as a condition in as many rungs as you like.

**2. It is a snapshot, not a live feed.**
Memory is written **once at the start of each scan**, during the read inputs step from section 4. If the physical switch changes state halfway through the program execution, the program does not see it until the next scan. This is the mechanism behind the one scan delay.

Put the two together and the earlier trap becomes obvious. **XIC asks "is the stored bit 1", not "is the switch physically closed".** The diagram shows exactly where that separation happens, at the "store in memory" step.

### On the addressing, X0

`X0` is generic and Mitsubishi style notation. Vendors differ:

| Vendor | Input address format | Example |
|---|---|---|
| Generic / Mitsubishi | X followed by a number | `X0` |
| **Siemens** | `%I` byte.bit | `%I0.0` |
| Allen-Bradley | Tag or module path | `Local:1:I.Data.0` |

Outputs follow the same pattern: `Y0` generic, `%Q0.0` on Siemens, and a tag on Allen-Bradley.

**For my Siemens path,** `%I0.0` is the first digital input and `%Q0.0` is the first digital output. Getting comfortable with the byte.bit notation early is worth doing, because it is the one piece of syntax that looks unfamiliar coming from generic tutorials.

---

### The trap that catches everyone

**XIC and XIO describe what the instruction examines in memory, not the physical state of the field device.**

This wording confuses nearly every beginner, so state it precisely:

- **XIC** asks: *is this bit currently 1?* If yes, pass power.
- **XIO** asks: *is this bit currently 0?* If yes, pass power.

The instruction has no idea whether the actual switch in the field is a normally open or normally closed device. It only reads the bit in the input image table.

### Why that distinction bites in the real world

A **stop button is wired normally closed** in industry, for fail safe reasons. While nobody is pressing it, the circuit is complete and the input bit is **1**.

So in the program you use an **XIC** for the stop button, even though it is a normally closed device.

| Field device | Physical wiring | Bit when idle | Instruction used |
|---|---|---|---|
| Start button | Normally open | 0 | **XIC**, becomes 1 when pressed |
| Stop button | **Normally closed** | **1** | **XIC**, drops to 0 when pressed |
| Emergency stop | **Normally closed** | **1** | **XIC**, drops to 0 when pressed |
| Proximity sensor detecting a part | Normally open | 0 | XIC |
| Fault or alarm bit, act when healthy | n/a, internal | 0 when healthy | **XIO** |

**Why stop buttons are wired normally closed:** if the wire breaks or the button fails, the circuit opens, the bit goes to 0, and the machine **stops**. Failure produces the safe outcome. A normally open stop button with a broken wire would leave you unable to stop the machine, which is exactly the wrong failure mode.

This is the same fail safe philosophy as live zero on a 4 to 20 mA loop, from section 6. Both are designed so a failure is detectable and lands in a safe state.

### The full worked example, one NO pushbutton, both instructions

This is the example that makes everything click. **One physical device**, a normally open pushbutton, examined two different ways. Four possible cases.

**Step 1, what the field device does**

| Pushbutton state | Contact | Bit value |
|---|---|---|
| Not pressed | Open | **0** |
| Pressed | Closed | **1** |

**Step 2, what each instruction does with that bit**

```
                XIC  ----| |----              XIO  ----|/|----
                (true when bit = 1)           (true when bit = 0)

              Pushbutton     Light          Pushbutton     Light
NOT       ----| |----------(   )----    ===|/|=========(   )===
PRESSED        bit = 0                       bit = 0
               FALSE                         TRUE
               Light OFF                     Light ON   <-- lit

              Pushbutton     Light          Pushbutton     Light
PRESSED   ===| |==========(   )===      ----|/|----------(   )----
               bit = 1                       bit = 1
               TRUE                          FALSE
               Light ON   <-- lit            Light OFF
```

**Step 3, the summary table**

| Pushbutton | Bit | XIC rung | Light | XIO rung | Light |
|---|:---:|---|:---:|---|:---:|
| Not pressed | 0 | FALSE | **OFF** | TRUE | **ON** ✅ |
| Pressed | 1 | TRUE | **ON** ✅ | FALSE | **OFF** |

### What this proves

**The same physical button produces opposite behaviour depending only on which instruction you choose.**

- With **XIC**, the light works normally. Press to turn on, release to turn off
- With **XIO**, the light is inverted. It sits on, and pressing the button turns it **off**

Nothing changed in the field. No rewiring, no different button. The behaviour was decided entirely in software.

This is the practical demonstration of the vocabulary point from the start of this section. **The field device is normally open. The instruction is your choice.** They are independent, and the instruction is what determines the logic.

**Useful way to hold it:** the XIO rung is the classic "on unless" pattern. Light on unless the button is pressed, motor running unless a fault is set, ready unless not healthy.

---

### Reading rungs, worked examples

Power flows left to right. All conditions in series must be true.

**Series, logical AND**
```
    Start          Stop           Motor
  ----| |---------| |------------(  )----
```
Motor runs only when the Start bit is 1 **and** the Stop bit is 1. Because Stop is wired normally closed, its bit is 1 while nobody is pressing it, so this rung behaves correctly.

**Parallel, logical OR**
```
   Button_A        Lamp
  ----| |-----+----(  )----
              |
   Button_B   |
  ----| |-----+
```
Lamp is on when Button A is 1 **or** Button B is 1.

**Using XIO to invert**
```
    Fault          Ready
  ----|/|-----------(  )----
```
Ready is on only when the Fault bit is **0**. The XIO inverts the condition, so this reads as "if not faulted, then ready".

### Vendor terminology, worth knowing

**XIC and XIO are Allen-Bradley terms.** Since I am going Siemens, the equivalents are:

| Concept | Allen-Bradley | Siemens |
|---|---|---|
| Pass when bit is 1 | XIC, Examine if Closed | Normally open contact |
| Pass when bit is 0 | XIO, Examine if Open | Normally closed contact |
| Set an output | OTE, Output Energise | Coil, assignment |

The **symbols and the logic are identical** because both follow IEC 61131-3. Only the naming differs. So learning XIC and XIO here transfers directly to TIA Portal, where they are simply called normally open and normally closed contacts.

### Quick recall
> Two vertical bars, pass when 1. Add a slash, pass when 0.
> The slash means "not".

### Relevant to me
This connects directly to the Triconex ladder logic I wrote at Fauji Fertilizer, and to the loop checking work. Knowing that a stop button reads as 1 while idle is exactly the sort of detail that matters when proving a loop end to end, because the "correct" reading at rest is the opposite of what a beginner would guess.

---

## 11a. Where a Trip Condition Belongs on a Rung

The same seal-in shape keeps reappearing. This is the general rule behind it, ahead of the worked examples.

**The three roles on a seal-in rung**

- **Enable group**, leftmost. Start OR seal-in, merged into one path
- **Trip condition**, middle. Sits after the merge, before the coil
- **Coil**, rightmost. The output itself

```
  Enable group                Trip                Coil
  (Start OR seal-in)      condition
  ----| |----+----------|/|--------------------(   )----
       |     |
      seal-in|
  ----| |----+
```

**Why the trip condition must sit after the merge, not inside a branch**

- If it sat only inside the Start branch, it would block a fresh start but not break an already-running seal-in loop
- If it sat only inside the seal-in branch, a plain Start press could re-energise straight around it
- Sitting on the trunk, after both paths merge, means it can shut things down regardless of which path is currently carrying power
- This is true whether the trip condition is a Stop button, a level sensor, a fault bit, or anything else that needs to override the hold

**Enable vs trip, not left vs right**

- Order along a straight series line does not change the logic, AND is commutative
- What differs is the **role**: a permissive that gates whether Start even matters goes first, leftmost
- A trip that must override an already-latched output goes after the merge, right before the coil
- Same instruction types, XIC or XIO, completely different placement logic depending on the job

---

## 12. Worked Examples: Seal-In in Practice

Two real style examples, each showing the same seal-in shape solving a different problem. Both use one physical sensor read two different ways in two different rungs, which is the section 10 lesson made concrete twice over.

> **Note on both examples.** These are teaching diagrams, simplified for the concept being shown, not complete industrial practicals. Real circuits would add things like start up permissives, sensor fault handling and timers.

---

### 12.1 Filling and Mixing Station

**The process:** press Start to fill a tank. When the level sensor trips, filling stops and mixing begins.

**Rung 1, Filling valve**

```
    Start PB                                Level sensor          Filling valve
  ----| |-----------+--------------------|/|------------------(   )----
                     |                     XIO
   Filling valve     |               "not full yet"
  ----| |------------+
     (seal-in)
```

**Rung 2, Mixer**

```
   Level sensor              Stop PB                Mixer
  ----| |------------------|/|--------------------(   )----
       XIC                   XIO
   "now full"
```

**Point by point**

- Start PB and the Filling valve seal-in are the **enable group**, merged before continuing right
- The Level sensor sits **after** that merge, in the **trip** position, exactly as section 11a describes
- On Rung 1 the Level sensor is read as **XIO**, true while the tank is not yet full. Once it trips, XIO goes false and breaks the filling rung
- On Rung 2 the **same physical sensor** is read as **XIC**, true only once the tank is full, enabling the Mixer
- One sensor, one memory bit, two opposite readings, two different rungs, on purpose
- The Level sensor here is functioning exactly like a Stop button. It is a trip condition, not a start condition, which is why it sits where a Stop normally sits

---

### 12.2 Conveyor with Status Lights

**The process:** Start and Stop run a conveyor. Two green lamps show running, one red lamp shows stopped.

**Rung 1, Conveyor**

```
    Stop PB                            Start PB               Conveyor
  ----|/|-----------+------------------| |------------------(   )----
                     |                   XIC
    Conveyor         |
  ----| |------------+
     (seal-in)
```

**Rung 2, Green lights**

```
    Conveyor                                    Green Light 1
  ----| |------------------------------+-----------(   )----
       XIC                             |
                                        |          Green Light 2
                                        +-----------(   )----
```

**Rung 3, Red light**

```
    Conveyor                            Stop red light
  ----|/|-----------------------------------(   )----
       XIO
```

**Point by point**

- Same seal-in shape as every other example: enable group on the left, trip condition after the merge, coil on the right
- Rung 2 reads the Conveyor bit as **XIC**. True while running, so both green lamps light together
- Rung 3 reads the **same Conveyor bit** as **XIO**. True while stopped, so the red lamp lights only when the conveyor is off
- Again, one internal bit, read two opposite ways, across two different rungs, driving opposite indicators
- **A wiring nuance worth flagging.** In Rung 1, Stop PB is drawn as **XIO**. For that to work as a stop, Stop PB must be wired **normally open**, idle bit 0, XIO true, so pressing it drives the bit to 1 and breaks the rung
- Section 11 taught the fail safe convention: wire Stop **normally closed** and read it with **XIC**, so a broken wire also stops the machine
- This diagram's version still works as a stop function, but it does **not** get that wire break protection. Worth noticing the difference rather than assuming every diagram follows the safest convention

---

### The one lesson both examples are really teaching

- **Position on the rung tells you the role.** Enable conditions sit left of the seal-in merge, trip conditions sit right of it, just before the coil
- **The same physical input can be read two different ways in two different rungs.** XIC in one place, XIO in another, same bit, opposite meaning, entirely by choice
- **Not every diagram uses the safest wiring convention.** Always check whether a Stop or trip condition is genuinely fail safe, normally closed with XIC, or just functionally working, normally open with XIO

---
---

Output instructions sit at the **right hand end** of a rung. They are what the rung actually does when its conditions are satisfied.

Three of them, and the difference between the first and the other two is the concept of **retention**.

### The three symbols

```
   OTE                OTL                OTU
  ----(  )----      ----( L )----      ----( U )----

  Output Energise   Output Latch       Output Unlatch
  follows the rung  sets to 1, holds   resets to 0
```

| | OTE | OTL | OTU |
|---|---|---|---|
| Name | Output Energise | Output Latch | Output Unlatch |
| Symbol | `----(  )----` | `----( L )----` | `----( U )----` |
| Rung TRUE | Sets bit to **1** | Sets bit to **1** | Sets bit to **0** |
| Rung FALSE | Sets bit to **0** | **Leaves it alone** | **Leaves it alone** |
| Retentive | **No** | **Yes** | **Yes** |
| Siemens name | Coil, assignment | **S**, Set | **R**, Reset |

---

### OTE, Output Energise

**The bit follows the rung exactly.** True energises it, false de-energises it. Nothing is remembered.

```
    Switch            Lamp
  ----| |------------(  )----
```
Hold the switch, the lamp is on. Release it, the lamp goes off immediately.

**The rule that catches beginners: never use the same OTE address on two rungs.**

```
   Start           Motor
  ----| |---------(  )----      <- rung 5

   Stop            Motor
  ----| |---------(  )----      <- rung 20, SAME address
```

This is **double coil syndrome**. Because the CPU executes top to bottom and writes outputs at the end of the scan, only the **last** rung to touch that address decides the final state. Rung 5 is effectively ignored. It is legal, it does not error, and it silently breaks your program. Most engineering software will warn you, and you should treat the warning as an error.

---

### Slide definitions, confirmed

- **Latch instruction (L):** to latch an output ON, output stays ON until the unlatch instruction becomes true
- **Unlatch instruction (U):** to unlatch a latch ON instruction with the same address

This confirms the OTL and OTU behaviour already covered below. Same address, two instructions, opposite jobs.

### OTL and OTU, latch and unlatch

These are **retentive**. They change the bit and then leave it, regardless of what the rung does afterwards.

**Simplest possible example, one rung**

```
   Pushbutton                Motor
  ----| |------------------( L )----
```

- Slide caption: **a latching instruction is used to keep the output ON**
- Tap the pushbutton for a moment, release it, the Motor bit stays 1
- Nothing in this single rung can turn it back off, that is the point being illustrated and also the danger
- This rung on its own is **incomplete**. It needs a matching OTU rung somewhere else in the program, or the output can never be switched off by the logic at all

**The three slide rules that complete the picture**

- **Rule 1.** Latch and unlatch instructions are always used **in pairs**
- **Rule 2.** Latch and unlatch instructions must have the **same reference address**
- **Rule 3.** Latch and unlatch instructions **do not have to be grouped together** in the ladder logic

**Rule 3 is the one worth sitting with.** OTL and OTU do not need to sit on adjacent rungs, or even nearby. They can be rungs apart, in different parts of the program, triggered by completely different conditions, so long as the **address matches**.

**The canonical two-rung example**

```
   Pushbutton 1                    Motor
  ----| |-------------------------( L )----          rung 1

   Pushbutton 2                    Motor
  ----| |-------------------------( U )----          rung 2
```

- **Rung 1**, Pushbutton 1, sets the Motor bit to 1 and holds it, regardless of where in the program rung 2 sits
- **Rung 2**, a completely separate condition, Pushbutton 2, resets the same Motor bit to 0
- Two different buttons, two different rungs, one shared address, that address is what links them, not their position in the program
- This is functionally identical to the Start and Stop seal-in pattern from section 11a, except the pairing is done through a shared **address** rather than through a **wired seal-in contact**

**Why this matters when reading someone else's program**

- You cannot assume an OTL and its matching OTU are near each other
- To find out what can turn a latched output off, **search the whole program for every instruction using that address**, not just the rungs around the one you are looking at
- This is a genuine debugging habit, not just a theory point. Missing a distant OTU is exactly how engineers get caught out by "the motor never switches off"

```
    Start            Motor
  ----| |---------( L )----      <- press once, motor stays on

    Stop             Motor
  ----| |---------( U )----      <- press once, motor stays off
```

Press Start for a moment and release it. The motor **stays running**, because OTL set the bit to 1 and nothing has reset it. Only the OTU rung can turn it off.

**They always come in pairs.** An OTL with no matching OTU is a bit you can never switch off, which is a bug rather than a design.

---

### The safety point, and it is a serious one

**Latched bits survive a CPU stop and a power cycle**, because they are stored in retentive memory.

That means if you latch a motor output and the plant loses power, when power returns **the motor can restart on its own**, with nobody having pressed anything. That is exactly the hazard that machine safety standards are written to prevent.

Rules that follow:
- **Never latch a safety critical output.** Emergency stops, safety interlocks and anything that could injure someone must not depend on a latched bit
- Prefer a **seal-in rung** over OTL and OTU for motor start and stop, because a seal-in de-energises naturally on power loss
- If you must latch, design an explicit start up routine that unlatches everything on first scan

### Seal-in, the preferred alternative

The same start and stop behaviour, built from OTE and a feedback contact rather than a latch:

```
    Start      Stop        Motor
  ----| |------| |---------(  )----
     |                       |
    Motor                    |
  ----| |------------------- +
```

The **Motor contact in parallel with Start** is the seal-in, sometimes called the holding contact. Once the motor is on, its own contact keeps the rung true after Start is released. Pressing Stop breaks the rung and it drops out.

**Why this is better than OTL and OTU:** it is a plain OTE, so it de-energises on power loss and cannot restart on its own. This is the single most important rung pattern in industrial ladder logic, and it is the first one worth being able to write from memory.

---

### Siemens equivalents

| Concept | Allen-Bradley | Siemens |
|---|---|---|
| Follows the rung | OTE | Coil `( )`, assignment |
| Set and hold | OTL | **S**, Set coil |
| Reset | OTU | **R**, Reset coil |
| Combined block | n/a | **SR** and **RS** flip flops |

Siemens also offers **SR** (set dominant) and **RS** (reset dominant) blocks, which combine set and reset into a single element and make the priority explicit. Worth knowing which one dominates, because that decides what happens when set and reset are both true at once. For anything safety related you want **reset dominant**.

---

### Quick reference

| Rung state | OTE | OTL | OTU |
|:---:|:---:|:---:|:---:|
| **TRUE** | bit → 1 | bit → 1 | bit → 0 |
| **FALSE** | bit → 0 | no change | no change |

> OTE forgets. OTL and OTU remember.
> If you latch it, you must plan how to unlatch it.

### Relevant to me
The Arduino based PLC module in my BSc final year project used exactly this pattern. Motor start and stop with a holding condition is the same seal-in logic, implemented in code rather than in ladder. And the safety reasoning here, that a latched output can restart itself after a power cut, is the same fail safe thinking behind normally closed stop buttons and live zero on a 4 to 20 mA loop.

---
---

# Appendix A. MCQ Revision Bank

Every course quiz question collected, grouped by topic. Answer in bold, with the reasoning underneath and the distractors explained where they are worth knowing.

**How to revise with this:** cover the answer, read the question, commit to an option, then check. The reasoning matters more than the answer, because interviewers ask the same concepts in open form.

---

## A1. PLC fundamentals

**Q. What is the primary function of a programmable logic controller in an industrial setting?**

- to handle customer service inquiries and manage databases
- to perform complex computational tasks and simulations
- **to continuously monitor the state of input devices and make decisions to control output devices** ✅
- to store large amounts of data for long term analysis

> This is the scan cycle described in plain language. Read inputs, decide, drive outputs, repeat. A PLC is not a general purpose computer and it is not a database. Note the word **continuously**, which is what distinguishes it from a PC running a program once.

---

**Q. You are setting up a PLC system and need to ensure it can handle both digital and analogue input signals. Which component of the PLC system will you primarily focus on?**

- the power supply
- **the I/O system** ✅
- the CPU
- the PLC programming software

> The I/O system is the interface to the physical world, and it is where you select modules by signal type. Digital input, digital output, analogue input, analogue output. The CPU runs the logic but does not determine what signal types the system can accept.

---

**Q. You are tasked with implementing a control system to regulate the flow of materials on a conveyor belt. Which key feature of a PLC makes it suitable?**

- capacity to store complex mathematical algorithms
- ability to act as a primary data storage system
- **high speed response to changes in input signals** ✅
- functionality to provide multimedia content to users

> A conveyor needs the controller to react the instant a sensor changes state. That is determinism and speed, which is exactly what a PLC is built for. Storage and heavy computation are what PCs and historians are for.

---

**Q. What is the purpose of the IEC 61131-3 international standard?**

- It sets safety protocols for industrial machinery operations
- **It defines the specifications required for languages that operate programmable logic controllers** ✅
- It provides guidelines for electrical wiring standards
- It outlines best practices for software development in general

> IEC 61131-3 standardises the five PLC programming languages: Ladder Diagram, Function Block Diagram, Structured Text, Sequential Function Chart and Instruction List.
>
> **Why this matters to me:** this standard is the reason skills transfer between vendors. Ladder logic learned on CODESYS works on Siemens and Allen-Bradley too.
>
> Do not confuse it with **IEC 61508 and 62061**, which are the functional **safety** standards.

---

## A2. Automation system levels

**Q. You are tasked with implementing a new automation system in a factory. Which level will you focus on if your main concern is ensuring that logic and design are correctly implemented?**

- OPC level
- Field level
- Device synchronization level
- **Control and Management levels** ✅

> Logic lives at the **control** level, in the PLC or DCS program. Design and visualisation live at the **management** level, in the HMI and SCADA. Together they are where implementation correctness is decided.
>
> Note that "OPC level" and "Device synchronization level" are not real levels in the hierarchy. They are invented distractors.

---

**Q. You are reviewing the HMI for a mixing project within a factory. What information would you expect the HMI to display?**

- The financial reports of the factory
- The list of employees working on the project
- The maintenance schedule for factory equipment
- **The status of the valve and the level of the tank** ✅

> An HMI shows **live process data**: valve open or closed, tank level, temperatures, pressures, alarms and setpoints. Financial reports and staff lists belong to business IT systems, not the operator interface. Maintenance schedules sit in a CMMS.
>
> Remember the levels. HMI is the management level view of the **process**, not of the business.

---

## A3. Communication protocols

**Q. What is ControlNet used for in industrial automation?**

- energy management in smart grids
- managing security protocols in IT systems
- **real time data transfer between devices on a network** ✅
- programming industrial robots

> ControlNet is a Rockwell and Allen-Bradley industrial network protocol. Its defining feature is **deterministic** real time communication, meaning data arrives within a guaranteed time window.
>
> The distractors map to other things: smart grids are IEC 61850, and robots are programmed in vendor software rather than over a network protocol.

---

## A4. OPC

**Q. You are configuring a network where an OPC client needs to connect to multiple OPC servers. What is this scenario called?**

- OPC tunneling
- OPC bridging
- **OPC aggregation** ✅
- OPC standardization

> **Aggregation** = one client, many servers, combined into a single view. This is how a plant wide SCADA screen shows data from a dozen different PLCs at once.

---

**Q. You need to connect an OPC client to an OPC server over a network. What method will you use?**

- **tunneling** ✅
- forwarding
- tagging
- bridging

> **Tunnelling** carries OPC data securely across a network, between sites or through a firewall. It was originally created to avoid the pain of configuring DCOM across networks in OPC Classic.

---

**Q. What functionality does the Cogent DataHub provide in an industrial automation environment?**

- **It can act as both an OPC server and client simultaneously** ✅
- It is solely used as an OPC server
- It only provides database management capabilities
- It functions exclusively as an OPC client

> Cogent DataHub is middleware that sits in the middle of an OPC architecture. Because it is **both server and client at once**, it can consume data from one system and republish it to another, which is what makes aggregation, tunnelling and bridging practical in one product.

---

### The four OPC scenarios, side by side

Worth memorising as a set, since the quiz tests them against each other.

| Scenario | Shape | One line |
|---|---|---|
| **Single** | 1 client to 1 server | The simplest case |
| **Aggregation** | 1 client to **many** servers | Combine many controllers into one view |
| **Tunnelling** | Across a **network** or firewall | Site to site, done securely |
| **Bridging** | **Server to server** | Direct transfer, no application in the middle |

**Memory hook:** Aggregate = gather many. Tunnel = go through. Bridge = span across between two of the same thing.

---

---

# Appendix B. Interview Quick Reference

**The three levels**
> Field instruments sense it, the PLC decides it, SCADA shows it.

**The four PLC components**
> Power supply, CPU, I/O system, software.

**The scan cycle**
> Read inputs, execute program, write outputs, repeat.

**Why 4 to 20 mA and not 0 to 20 mA**
> Live zero. 0 mA means a broken loop, not a zero reading. Built in fault detection.

**PLC vs DCS in one line**
> PLC for fast discrete machine control, DCS for continuous plant wide process control. The distinction is blurring.

**Management level vs control level**
> Management level is supervisory. It requests, the PLC executes. Safety critical control never lives at the management level.

**PROFIBUS vs PROFINET**
> PROFIBUS is the older serial fieldbus, one shared cable for many devices. PROFINET is the modern Ethernet based successor.

**What HART adds**
> Bidirectional digital diagnostics layered over the existing 4 to 20 mA loop, with no rewiring.

**The two CPU modes**
> Programming mode downloads the logic. Run mode executes it. In programming mode the plant is not being controlled and outputs fall to a safe state.

**What forcing is, and the catch**
> Overriding an input or output regardless of the real field signal, used for commissioning and loop checks. The program is no longer reacting to reality, so forces must be documented and removed before handover.

**Standard signal values**
> Analogue: 4 to 20 mA or 0 to 10 V DC, both directions. Digital: 24 V DC is the industrial standard, with 110 or 230 V AC on older or mains powered equipment.

**Sinking vs sourcing**
> Sourcing supplies current out and matches PNP. Sinking receives current and matches NPN. A sourcing device must pair with a sinking one, otherwise the input never registers.

**Why a PLC output cannot run a motor**
> Outputs are low current. The output energises a contactor coil, and the contactor switches the motor power circuit. The PLC does control, not power.

**What OPC is for**
> A vendor neutral standard that lets controllers from different manufacturers publish data to one place, so any HMI, SCADA or database can read it without a custom driver per device.

**OPC server vs client**
> Server is the parent, it provides the data. Client is the child, it requests and uses it. One server serves many clients.

**OPC Classic vs OPC UA**
> Classic was built on Windows COM and DCOM. OPC UA is platform independent with built in security, and is the modern Industry 4.0 standard.

**What SCADA stands for and does**
> Supervisory Control and Data Acquisition. It acquires data from across the plant and provides supervisory control, meaning it requests actions rather than executing them. The PLC still does the controlling.

**HMI vs SCADA**
> HMI is local, usually one machine or area, often a physical panel. SCADA is plant wide software with trending, alarming, logging and history. Every SCADA includes HMI functionality, but not every HMI is SCADA.

**PLC vs RTU**
> PLC is for fast complex control logic on site. RTU is for wide area telemetry at genuinely remote locations, often low power and on radio or cellular. The distinction is fading, but the term still appears in water and utilities job adverts.

**XIC vs XIO**
> XIC `----| |----` is TRUE when the bit is **1**. XIO `----|/|----` is TRUE when the bit is **0**. Exact opposites. The slash means not. Both examine the bit in memory, not the physical state of the field device.

**OTE vs OTL vs OTU**
> OTE `( )` follows the rung, true sets the bit to 1 and false sets it to 0. OTL `( L )` sets to 1 and holds. OTU `( U )` resets to 0. OTL and OTU are retentive and always used as a pair.

**What is double coil syndrome**
> The same OTE address written on two rungs. The CPU executes top to bottom and writes outputs at the end of the scan, so only the last rung decides the final state. It does not error, it just silently breaks the logic.

**Why not latch a motor output**
> Latched bits are retentive and survive a power cycle, so the motor could restart on its own when power returns with nobody pressing anything. Use a seal-in rung instead, which de-energises naturally on power loss.

**What is a seal-in rung**
> Start in parallel with a contact of the output itself, in series with a normally closed stop. The output's own contact holds the rung true after the start button is released. The most important pattern in industrial ladder logic.

**How are OTL and OTU linked if not by position**
> By address, not by location. They are always used in pairs and must share the same reference address, but they do not have to be grouped together in the program. To find what can turn a latched output off, search the whole program for that address, not just nearby rungs.

**How does a field signal reach a rung**
> Physical device, then input module which converts it to a logic bit, then input signal memory which stores it in the input image table, then the ladder instruction reads that stored bit. The program reads memory, never the device.

**Siemens addressing**
> %I0.0 is the first digital input, %Q0.0 the first digital output. Byte dot bit notation.

**Why is a stop button programmed with an XIC when it is a normally closed device**
> Because it is wired normally closed, its input bit reads 1 while nobody is pressing it. Pressing it drops the bit to 0 and breaks the rung. Wiring it normally closed means a broken wire also stops the machine, so failure lands in the safe state.

**Why SCADA is a security concern**
> It connects the control network to wider networks, so it needs segmentation, firewalls between control and business networks, and a DMZ for data that IT needs. Stuxnet targeted exactly this kind of system.

---

# Appendix C. Interview Questions and Model Answers

Questions a graduate control and instrumentation or automation interview is likely to include, based on everything covered so far. Answers written in my own voice, using my actual experience.

---

## C1. Technical fundamentals

**Q. What is a PLC and what does it do?**
> A Programmable Logic Controller is an industrial computer that sits at the control level of an automation system. It reads signals from field instruments, processes them against programmed logic, and drives outputs to devices like valves, motors and contactors. It is built to be rugged and deterministic, so it runs reliably in a plant environment for years.

**Q. Explain the PLC scan cycle.**
> The CPU repeats four steps continuously. It reads all inputs and stores them in an input image table, executes the program top to bottom using that snapshot, writes the outputs, then does housekeeping like diagnostics and comms before repeating.
>
> The important consequence is that the program works from a snapshot, not live inputs, and outputs do not energise the instant a rung solves. They update at the end of the scan. That is what causes one scan delays, and it is why rung order matters.

**Q. What are the main components of a PLC?**
> Power supply, CPU, I/O system and software. The power supply converts mains down to 24 V DC, the CPU holds the memory and runs the scan cycle, the I/O system interfaces with the field, and the software is both the engineering tool like TIA Portal and the program itself.

**Q. What is the difference between a PLC and a DCS?**
> A PLC is optimised for fast discrete machine control over one machine or area. A DCS is built for continuous process control across a whole plant with many control loops, with the controllers distributed but centrally managed.
>
> In practice the distinction is blurring, because modern PLCs handle process control well and DCS platforms use PLC style logic. My own exposure was DCS and ESD at a fertilizer plant, and the logic thinking transfers directly.

**Q. What are the three levels of an automation system?**
> Device level is the field instruments and actuators. Control level is the PLC or DCS running the logic. Management or application level is SCADA, HMI and historians.
>
> The short version I use is that field instruments sense it, the PLC decides it, and SCADA shows it.

**Q. Can SCADA control a motor directly?**
> No. The management level is supervisory. It sends a request down to the PLC, and the PLC executes the actual control. The PLC keeps running its logic even if SCADA goes offline. That separation is deliberate, and it is why safety critical control never lives at the management level.

**Q. What are the CPU operating modes?**
> Broadly programming mode and run mode. In programming mode, called STOP on Siemens and PROG on Allen-Bradley, the logic is halted and outputs go to a safe state, which is when you download a program or change hardware configuration. In run mode the scan cycle executes and outputs are live.
>
> Allen-Bradley also has a REM position which hands mode control to the software so it can be switched remotely.

**Q. What are the IEC 61131-3 languages?**
> Ladder Diagram, Function Block Diagram, Structured Text, Sequential Function Chart and Instruction List. Ladder and Function Block are the two I have used, programming Triconex safety systems during my placements.

---

## C2. I/O and signals

**Q. What are the four types of I/O?**
> Digital input, digital output, analogue input and analogue output. Digital is on or off, like a limit switch or a contactor. Analogue is a continuous value, like a pressure transmitter or a valve positioner.

**Q. What are the standard analogue signal ranges?**
> 4 to 20 mA and 0 to 10 V DC. 4 to 20 mA is the process industry standard.

**Q. Why 4 to 20 mA and not 0 to 20 mA?**
> Live zero. 4 mA represents zero percent of range, so a reading of 0 mA can only mean a broken loop or a dead instrument. If the range started at 0 mA there would be no way to tell a genuine zero from a failed loop. It is fault detection built into the signal standard.

**Q. Why is a current loop better than a voltage signal?**
> Current is unaffected by voltage drop along the cable and is far more immune to induced electrical noise, so it works over long runs in an electrically noisy plant. Voltage signals degrade with distance and pick up noise, so they are used for short runs on machines.

**Q. What are the typical digital voltages?**
> 24 V DC is the industrial standard for both inputs and outputs. Older or mains powered equipment uses 110 or 230 V AC.

**Q. What types of digital output module are there and when would you use each?**
> Transistor, relay and triac. Transistor for fast frequently switched DC loads like solenoid valves. Relay when you need a volt free contact, when the load is AC, or when the load voltage differs from the PLC supply. Triac for AC loads switched often enough that a relay would wear out.

**Q. Can a PLC output drive a motor directly?**
> No. Outputs are low current. The output energises a contactor coil and the contactor switches the motor power circuit. The PLC does control, not power.

**Q. Explain sinking and sourcing.**
> A sourcing device supplies current out, which corresponds to a PNP sensor. A sinking device receives current and provides the path to 0 V, which corresponds to NPN. They must pair opposite, so a PNP sourcing sensor goes to a sinking input card.
>
> If you get it backwards the input simply never registers and there is no obvious fault to see, which makes it a common commissioning problem. PNP sourcing is the norm in Europe.

**Q. What is intrinsically safe I/O and why does it matter?**
> It limits the electrical energy going into the field so it cannot ignite an explosive atmosphere. It is required in hazardous areas, which is directly relevant to the fertilizer, chemical and oil and gas environments I have worked in and am targeting.

---

## C3. Communication

**Q. Which industrial protocols do you know?**
> On the Siemens side, PROFINET which is the modern Ethernet based standard, and PROFIBUS which is the older fieldbus but still very widely installed. More broadly Modbus, HART and Foundation Fieldbus on the instrumentation side, and EtherNet/IP and ControlNet on the Rockwell side.

**Q. What is HART and what makes it useful?**
> Highway Addressable Remote Transducer. It layers a bidirectional digital signal on top of the existing 4 to 20 mA current loop, so the analogue signal still carries the process value while the digital signal carries configuration, diagnostics and secondary values.
>
> The practical benefit is that no new wiring is needed. An engineer can configure, calibrate and diagnose an instrument remotely instead of walking out to it, and the device health data feeds straight into predictive maintenance.

**Q. What is the advantage of PROFIBUS over traditional wiring?**
> It uses a single shared bus cable with devices connected along it, each with its own address, rather than running an individual pair from every instrument back to the I/O card. That massively reduces cabling, cable trays, marshalling terminations and installation cost.

**Q. What is the difference between PROFIBUS and PROFINET?**
> PROFIBUS is the older serial fieldbus. PROFINET is the modern Ethernet based successor. New Siemens projects specify PROFINET, but PROFIBUS is still installed everywhere, so both are worth knowing.

**Q. What is OPC and why does it exist?**
> Open Platform Communications. It is a vendor neutral standard for exchanging data. Without it, every HMI, SCADA package or database would need a custom driver written for every controller brand it talks to.
>
> With OPC, controllers publish their data through a common layer and any application can read it the same way, regardless of manufacturer.

**Q. How is OPC implemented?**
> In server and client pairs. The server is the parent, it sits close to the controller and provides the data. The client is the child, it requests and uses that data, so an HMI, SCADA system, historian or database. One server can serve many clients.
>
> There are four connection scenarios: a single client to server connection, aggregation where one client pulls from multiple servers, tunnelling across a network or firewall, and bridging which moves data server to server.

**Q. What is the difference between OPC Classic and OPC UA?**
> OPC Classic was built on Microsoft COM and DCOM, so it was Windows only and the security was weak. OPC UA is platform independent, runs on Windows, Linux, embedded devices and cloud, and has encryption, authentication and certificates built in. UA is the modern Industry 4.0 standard and the one worth investing in.

---

## C4. Questions about my background

**Q. What is your greatest achievement to date?**
> During a plant turnaround at Fauji Fertilizer, I was responsible for terminating and loop checking DCS and ESD field wiring across multiple marshalling cabinets. I delivered 100 percent accurate cable tagging with zero errors, which supported a clean commissioning and minimised downtime.
>
> What makes it my greatest achievement is not the technical work itself but doing it to a standard where safety critical wiring had no room for mistakes, under live turnaround pressure.

**Q. You are a graduate. What real plant experience do you actually have?**
> Two placements at Fauji Fertilizer as an Instrumentation and Control Engineer, including a full plant turnaround. I supervised termination and loop checking of DCS and ESD field wiring, calibrated flow, pressure, level and temperature transmitters using standard procedures, programmed Triconex safety PLCs in Ladder and Function Block Diagram, and mapped the plant wide DCS and ESD architecture including marshalling cabinet layouts.
>
> So I have worked on live safety critical systems in a process plant, which is unusual for a graduate.

**Q. Why control and instrumentation rather than general electrical?**
> It is where my strongest results and my strongest experience line up. I took a Distinction in Industrial Process Control in my MSc, my BSc final year project was building an Arduino based PLC module with an HMI and IoT connectivity, and my placements were both instrumentation and control. It is also the area I find genuinely interesting, because it sits between the physical process and the software.

**Q. Tell me about your final year project.**
> I designed and built a programmable logic controller module on Arduino that controlled stepper, servo and DC motors for speed and direction, aimed at small scale industrial and IoT applications. I developed an HMI dashboard for real time operator monitoring and added IoT connectivity through a mobile app for remote control.
>
> Building a controller from first principles rather than just configuring one taught me what is actually happening inside a PLC, which has made learning commercial platforms much faster.

**Q. You have a machine learning dissertation. Is that not a different career?**
> I see it as the same career one level up. My dissertation built ANN and LSTM models for battery state of health and remaining useful life, benchmarked against Kalman filtering. That is predictive maintenance, and predictive maintenance runs on plant data acquired at the management level through systems like OPC UA and historians.
>
> So the control skills and the data skills connect directly. A PLC generates the data, OPC UA exposes it, and Python consumes it. Being able to work at both ends is the combination I am deliberately building.

**Q. Which PLC platform do you know?**
> My hands on plant experience is Triconex safety systems in Ladder and Function Block. I am now building formal skills on Siemens TIA Portal, because Siemens leads the UK market and dominates the process industries and the Middle East EPC projects I am targeting.
>
> The fundamentals are IEC 61131-3 standardised, so the logic transfers. I have deliberately gone deep on one platform rather than shallow on several.

**Q. Where do you see yourself in five years?**
> Working as a control and instrumentation or automation engineer on process plant, ideally with chartership underway, and specialising in the overlap between control systems and plant data. Predictive maintenance and condition monitoring are where I think the field is heading, and it is where my background gives me an advantage.

**Q. Do you need visa sponsorship?**
> No. I am on the UK Graduate Route with full right to work for two years and no sponsorship required.

---

## C5. Questions to ask them

Always have three ready. These work well:

1. What PLC and SCADA platforms does the team standardise on, and is there any migration planned?
2. What does the first six months look like for a graduate engineer here, and is there support toward chartership?
3. How much of the role is design and programming versus commissioning and site work?
4. Is there any work happening around plant data, condition monitoring or predictive maintenance?

That last one is worth asking. It signals the data side of my background without me having to force it into an answer.

---

## C6. Preparation notes

- **Know my own CV cold.** Every claim on it is fair game
- **Have numbers ready.** 100 percent accurate cable tagging, zero errors, Distinction grades
- **Use STAR** for behavioural questions: Situation, Task, Action, Result
- **Say when I do not know something**, then say how I would find out. In control engineering, guessing is a genuine safety concern and interviewers know it
- **Do not oversell the PLC programming.** Say honestly that my plant experience was Triconex and that I am actively building TIA Portal skills. Enthusiasm plus honesty beats an exaggeration that collapses under one follow up question

---
