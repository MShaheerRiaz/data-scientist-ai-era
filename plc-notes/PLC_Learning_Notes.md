# PLC Learning Notes

**Muhammad Shaheer Riaz**
MSc Electrical and Electronics Engineering, Anglia Ruskin University

**Course:** Introduction to PLC and Industrial Automation (Zahraa Khalil, LinkedIn Learning)
**Path:** Become a PLC Developer
**Target platform:** Siemens TIA Portal

---

## Contents

1. [Automation System Levels](#note-01-automation-system-levels)
2. [PLCs and Distributed Control Systems](#note-02-programmable-logic-controllers-and-distributed-control-systems)
3. [Management Level](#note-03-management-level)
4. [Industrial Communication Protocols](#note-04-industrial-communication-protocols)

---

## Note 01. Automation System Levels

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

## Note 02. Programmable Logic Controllers and Distributed Control Systems

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

## Note 03. Management Level

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

## Note 04. Industrial Communication Protocols

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

### Quiz answers captured

**Q. What is ControlNet used for in industrial automation?**
> Real time data transfer between devices on a network

**Q. Implementing a new automation system, main concern is that logic and design are correctly implemented. Which level do you focus on?**
> Control and Management levels

### What to prioritise given my Siemens path
1. **PROFINET** and **PROFIBUS**, non negotiable for Siemens work
2. **HART** and **Foundation Fieldbus**, directly relevant to my instrumentation background
3. **Modbus**, universal and quick to pick up
4. **OPC UA**, the bridge between control and my Python and data work
5. EtherNet/IP and ControlNet, only if I move toward Allen-Bradley

---
