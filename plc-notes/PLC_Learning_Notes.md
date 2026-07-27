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

**Appendix**

- [Quiz Answers](#appendix-a-quiz-answers)
- [Interview Quick Reference](#appendix-b-interview-quick-reference)

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

**Slide definition:** A standard for a secure and reliable exchange of data.

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

# Appendix A. Quiz Answers

| Question | Answer |
|---|---|
| What is ControlNet used for in industrial automation? | Real time data transfer between devices on a network |
| Implementing a new automation system, main concern is that logic and design are correctly implemented. Which level do you focus on? | Control and Management levels |

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

---
