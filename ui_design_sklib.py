from collections import defaultdict
from skidl import Pin, Part, Alias, SchLib, SKIDL, TEMPLATE

from skidl.pin import pin_types

SKIDL_lib_version = '0.0.1'

ui_design = SchLib(tool=SKIDL).add_parts(*[
        Part(**{ 'name':'Conn_02x10_Odd_Even', 'dest':TEMPLATE, 'tool':SKIDL, 'aliases':Alias({'Conn_02x10_Odd_Even'}), 'ref_prefix':'J', 'fplist':[''], 'footprint':'Connector_PinHeader_1.27mm:PinHeader_2x10_P1.27mm_Vertical', 'keywords':'connector', 'description':'Generic connector, double row, 02x10, odd/even pin numbering scheme (row 1 odd numbers, row 2 even numbers), script generated (kicad-library-utils/schlib/autogen/connector/)', 'datasheet':'', 'pins':[
            Pin(num='1',name='Pin_1',func=pin_types.PASSIVE,unit=1),
            Pin(num='2',name='Pin_2',func=pin_types.PASSIVE,unit=1),
            Pin(num='3',name='Pin_3',func=pin_types.PASSIVE,unit=1),
            Pin(num='4',name='Pin_4',func=pin_types.PASSIVE,unit=1),
            Pin(num='5',name='Pin_5',func=pin_types.PASSIVE,unit=1),
            Pin(num='6',name='Pin_6',func=pin_types.PASSIVE,unit=1),
            Pin(num='7',name='Pin_7',func=pin_types.PASSIVE,unit=1),
            Pin(num='8',name='Pin_8',func=pin_types.PASSIVE,unit=1),
            Pin(num='9',name='Pin_9',func=pin_types.PASSIVE,unit=1),
            Pin(num='10',name='Pin_10',func=pin_types.PASSIVE,unit=1),
            Pin(num='11',name='Pin_11',func=pin_types.PASSIVE,unit=1),
            Pin(num='12',name='Pin_12',func=pin_types.PASSIVE,unit=1),
            Pin(num='13',name='Pin_13',func=pin_types.PASSIVE,unit=1),
            Pin(num='14',name='Pin_14',func=pin_types.PASSIVE,unit=1),
            Pin(num='15',name='Pin_15',func=pin_types.PASSIVE,unit=1),
            Pin(num='16',name='Pin_16',func=pin_types.PASSIVE,unit=1),
            Pin(num='17',name='Pin_17',func=pin_types.PASSIVE,unit=1),
            Pin(num='18',name='Pin_18',func=pin_types.PASSIVE,unit=1),
            Pin(num='19',name='Pin_19',func=pin_types.PASSIVE,unit=1),
            Pin(num='20',name='Pin_20',func=pin_types.PASSIVE,unit=1)], 'unit_defs':[] }),
        Part(**{ 'name':'C', 'dest':TEMPLATE, 'tool':SKIDL, 'aliases':Alias({'C'}), 'ref_prefix':'C', 'fplist':[''], 'footprint':'Capacitor_SMD:C_0805_2012Metric', 'keywords':'cap capacitor', 'description':'Unpolarized capacitor', 'datasheet':'', 'pins':[
            Pin(num='1',func=pin_types.PASSIVE,unit=1),
            Pin(num='2',func=pin_types.PASSIVE,unit=1)], 'unit_defs':[] }),
        Part(**{ 'name':'Conn_01x08', 'dest':TEMPLATE, 'tool':SKIDL, 'aliases':Alias({'Conn_01x08'}), 'ref_prefix':'J', 'fplist':[''], 'footprint':'Connector_PinSocket_2.54mm:PinSocket_1x08_P2.54mm_Vertical', 'keywords':'connector', 'description':'Generic connector, single row, 01x08, script generated (kicad-library-utils/schlib/autogen/connector/)', 'datasheet':'', 'pins':[
            Pin(num='1',name='Pin_1',func=pin_types.PASSIVE,unit=1),
            Pin(num='2',name='Pin_2',func=pin_types.PASSIVE,unit=1),
            Pin(num='3',name='Pin_3',func=pin_types.PASSIVE,unit=1),
            Pin(num='4',name='Pin_4',func=pin_types.PASSIVE,unit=1),
            Pin(num='5',name='Pin_5',func=pin_types.PASSIVE,unit=1),
            Pin(num='6',name='Pin_6',func=pin_types.PASSIVE,unit=1),
            Pin(num='7',name='Pin_7',func=pin_types.PASSIVE,unit=1),
            Pin(num='8',name='Pin_8',func=pin_types.PASSIVE,unit=1)], 'unit_defs':[] }),
        Part(**{ 'name':'R', 'dest':TEMPLATE, 'tool':SKIDL, 'aliases':Alias({'R'}), 'ref_prefix':'R', 'fplist':[''], 'footprint':'Resistor_SMD:R_0603_1608Metric', 'keywords':'R res resistor', 'description':'Resistor', 'datasheet':'', 'pins':[
            Pin(num='1',func=pin_types.PASSIVE,unit=1),
            Pin(num='2',func=pin_types.PASSIVE,unit=1)], 'unit_defs':[] }),
        Part(**{ 'name':'RotaryEncoder', 'dest':TEMPLATE, 'tool':SKIDL, 'aliases':Alias({'RotaryEncoder'}), 'ref_prefix':'SW', 'fplist':[''], 'footprint':'supply1:RotaryEncoder_Alps_EC10E_Horizontal', 'keywords':'rotary switch encoder', 'description':'Rotary encoder, dual channel, incremental quadrate outputs', 'datasheet':'', 'pins':[
            Pin(num='A',name='A',func=pin_types.PASSIVE,unit=1),
            Pin(num='B',name='B',func=pin_types.PASSIVE,unit=1),
            Pin(num='C',name='C',func=pin_types.PASSIVE,unit=1)], 'unit_defs':[] }),
        Part(**{ 'name':'SW_Push', 'dest':TEMPLATE, 'tool':SKIDL, 'aliases':Alias({'SW_Push'}), 'ref_prefix':'SW', 'fplist':[''], 'footprint':'Button_Switch_THT:SW_TH_Tactile_Omron_B3F-106x', 'keywords':'switch normally-open pushbutton push-button', 'description':'Push button switch, generic, two pins', 'datasheet':'', 'pins':[
            Pin(num='1',name='1',func=pin_types.PASSIVE),
            Pin(num='2',name='2',func=pin_types.PASSIVE)], 'unit_defs':[] }),
        Part(**{ 'name':'TCA9535PWR', 'dest':TEMPLATE, 'tool':SKIDL, 'aliases':Alias({'TCA9535PWR'}), 'ref_prefix':'U', 'fplist':['Package_SO:TSSOP-24_4.4x7.8mm_P0.65mm'], 'footprint':'Package_SO:TSSOP-24_4.4x7.8mm_P0.65mm', 'keywords':'ti parallel port', 'description':'16-bit I/O expander, I2C and SMBus interface, interrupts, w/o pull-ups, TSSOP-24 package', 'datasheet':'http://www.ti.com/lit/ds/symlink/tca9535.pdf', 'pins':[
            Pin(num='1',name='~{INT}',func=pin_types.OPENCOLL,unit=1),
            Pin(num='2',name='A1',func=pin_types.INPUT,unit=1),
            Pin(num='3',name='A2',func=pin_types.INPUT,unit=1),
            Pin(num='4',name='P00',func=pin_types.BIDIR,unit=1),
            Pin(num='5',name='P01',func=pin_types.BIDIR,unit=1),
            Pin(num='6',name='P02',func=pin_types.BIDIR,unit=1),
            Pin(num='7',name='P03',func=pin_types.BIDIR,unit=1),
            Pin(num='8',name='P04',func=pin_types.BIDIR,unit=1),
            Pin(num='9',name='P05',func=pin_types.BIDIR,unit=1),
            Pin(num='10',name='P06',func=pin_types.BIDIR,unit=1),
            Pin(num='11',name='P07',func=pin_types.BIDIR,unit=1),
            Pin(num='12',name='GND',func=pin_types.PWRIN,unit=1),
            Pin(num='13',name='P10',func=pin_types.BIDIR,unit=1),
            Pin(num='14',name='P11',func=pin_types.BIDIR,unit=1),
            Pin(num='15',name='P12',func=pin_types.BIDIR,unit=1),
            Pin(num='16',name='P13',func=pin_types.BIDIR,unit=1),
            Pin(num='17',name='P14',func=pin_types.BIDIR,unit=1),
            Pin(num='18',name='P15',func=pin_types.BIDIR,unit=1),
            Pin(num='19',name='P16',func=pin_types.BIDIR,unit=1),
            Pin(num='20',name='P17',func=pin_types.BIDIR,unit=1),
            Pin(num='21',name='A0',func=pin_types.INPUT,unit=1),
            Pin(num='22',name='SCL',func=pin_types.INPUT,unit=1),
            Pin(num='23',name='SDA',func=pin_types.BIDIR,unit=1),
            Pin(num='24',name='VCC',func=pin_types.PWRIN,unit=1)], 'unit_defs':[] }),
        Part(**{ 'name':'TestPoint', 'dest':TEMPLATE, 'tool':SKIDL, 'aliases':Alias({'TestPoint'}), 'ref_prefix':'TP', 'fplist':[''], 'footprint':'TestPoint:TestPoint_Pad_D1.0mm', 'keywords':'test point tp', 'description':'test point', 'datasheet':'', 'pins':[
            Pin(num='1',name='1',func=pin_types.PASSIVE,unit=1)], 'unit_defs':[] }),
        Part(**{ 'name':'LED', 'dest':TEMPLATE, 'tool':SKIDL, 'aliases':Alias({'LED'}), 'ref_prefix':'D', 'fplist':[''], 'footprint':'LED_THT:LED_D3.0mm', 'keywords':'LED diode', 'description':'Light emitting diode', 'datasheet':'', 'pins':[
            Pin(num='1',name='K',func=pin_types.PASSIVE,unit=1),
            Pin(num='2',name='A',func=pin_types.PASSIVE,unit=1)], 'unit_defs':[] }),
        Part(**{ 'name':'Conn_01x04', 'dest':TEMPLATE, 'tool':SKIDL, 'aliases':Alias({'Conn_01x04'}), 'ref_prefix':'J', 'fplist':[''], 'footprint':'Connector_JST:JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical', 'keywords':'connector', 'description':'Generic connector, single row, 01x04, script generated (kicad-library-utils/schlib/autogen/connector/)', 'datasheet':'', 'pins':[
            Pin(num='1',name='Pin_1',func=pin_types.PASSIVE,unit=1),
            Pin(num='2',name='Pin_2',func=pin_types.PASSIVE,unit=1),
            Pin(num='3',name='Pin_3',func=pin_types.PASSIVE,unit=1),
            Pin(num='4',name='Pin_4',func=pin_types.PASSIVE,unit=1)], 'unit_defs':[] }),
        Part(**{ 'name':'Buzzer', 'dest':TEMPLATE, 'tool':SKIDL, 'aliases':Alias({'Buzzer'}), 'ref_prefix':'BZ', 'fplist':[''], 'footprint':'Buzzer_Beeper:Buzzer_12x9.5RM7.6', 'keywords':'quartz resonator ceramic', 'description':'Buzzer, polarized', 'datasheet':'', 'pins':[
            Pin(num='1',name='+',func=pin_types.PASSIVE,unit=1),
            Pin(num='2',name='-',func=pin_types.PASSIVE,unit=1)], 'unit_defs':[] }),
        Part(**{ 'name':'2N7002', 'dest':TEMPLATE, 'tool':SKIDL, 'aliases':Alias({'2N7002'}), 'ref_prefix':'Q', 'fplist':['', 'Package_TO_SOT_SMD:SOT-23'], 'footprint':'Package_TO_SOT_SMD:SOT-23', 'keywords':'N-Channel Switching MOSFET', 'description':'0.115A Id, 60V Vds, N-Channel MOSFET, SOT-23', 'datasheet':'https://www.onsemi.com/pub/Collateral/NDS7002A-D.PDF', 'pins':[
            Pin(num='1',name='G',func=pin_types.INPUT,unit=1),
            Pin(num='2',name='S',func=pin_types.PASSIVE,unit=1),
            Pin(num='3',name='D',func=pin_types.PASSIVE,unit=1)], 'unit_defs':[] }),
        Part(**{ 'name':'D_Schottky', 'dest':TEMPLATE, 'tool':SKIDL, 'aliases':Alias({'D_Schottky'}), 'ref_prefix':'D', 'fplist':[''], 'footprint':'Diode_SMD:D_SMA', 'keywords':'diode Schottky', 'description':'Schottky diode', 'datasheet':'', 'pins':[
            Pin(num='1',name='K',func=pin_types.PASSIVE,unit=1),
            Pin(num='2',name='A',func=pin_types.PASSIVE,unit=1)], 'unit_defs':[] }),
        Part(**{ 'name':'MountingHole', 'dest':TEMPLATE, 'tool':SKIDL, 'aliases':Alias({'MountingHole'}), 'ref_prefix':'H', 'fplist':[''], 'footprint':'MountingHole:MountingHole_3.2mm_M3', 'keywords':'mounting hole', 'description':'Mounting Hole without connection', 'datasheet':'' })])