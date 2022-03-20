#!/usr/bin/env python3
"""
mts_dumper.py
Copyright (C) 2022  Sophia Kovaleva (https://github.com/kosonya, sophia.m.kovaleva@gmail.com)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""



__version__ = "0.0.1"

import argparse
import math
import functools
import textwrap
import collections

notes = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
eqtemp12_cents = [0.0, 100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0, 900.0, 1000.0, 1100.0] 
midi_note_range = (0, 127)
midi_reference_note = {"ID": 60, "note": "C", "octave": 4} 
midi_max_cents_value = (2**14 - 1)
midi_max_cents_offset = 100.0 #open interval!
base_octave = 4
cents_in_octave = 1200.0
bytes_header = 8
bytes_per_note = 4


def main():
    global notes
    parser = argparse.ArgumentParser(description="Convert an entered 12 tone chromatic scale into MIDI 1.0 MTS compatible real-time SysEx message and outputs it " +\
                                                 "as a copy-pasteable HEX dump. Note that some editors (e.g. Reaper v6.49) may auto-complete F0 and F7 for the SysEx message. " +\
                                                 "The format is for single-note tuning, but it actually retunes all 128 MIDI notes. If your synth supports octave-based tuning, use Scala." +\
                                                 "Or use MIDI 2.0 per-note pitch bending. Also use Scala if you need anything other than 12-tone scales or 2:1 octaves.")
                                                 
    parser.add_argument("scale", metavar="STEP", type=str, nargs=12, help="Steps of the 12-tone scale. Can be either ratios (default) or cents. Can be from the first step or from each other. Base 10. Format: [+,-]digits[.digits[<:|/>digits[.digits]]]. Enter x instead "+\
                                                                          "of a step if you don't want to retune it.")
    parser.add_argument("-v", "--version", action="version", version="%(prog)s version {version}".format(version=__version__))
    parser.add_argument("--print-cents", dest="print_cents", action="store_true", help="Output cents of the scale (relative to root) instead of a HEX dump.")
    parser.add_argument("--dont-print-cents", dest="print_cents", action="store_false", help="Don't pring stuff")
    parser.set_defaults(print_cents=False)
    parser.add_argument("--input-cents", dest="input_cents", action="store_true", help="Treat arguments as cents rather than ratios by default.")
    parser.add_argument("--input-ratios", dest="input_cents", action="store_false", help="Treat arguments as cents rather than ratios by default.")
    parser.set_defaults(input_cents=False)
    parser.add_argument("--starting-note", metavar="NOTE", type=str, action="store", default="C", help="Note to start the scale with, if not C. Possible values: {}".format(notes))
    parser.add_argument("--from-each-other", dest="from_each_other", action="store_true", help="Treat intervals or cents as being relative to each other rather than root")
    parser.add_argument("--from-root", dest="from_each_other", action="store_false", help="Treat intervals or cents as being relative to the root.")
    parser.set_defaults(from_each_other=False)
    parser.add_argument("--device-id", metavar="ID", type=int, action="store", default=127, help="Device ID to craft the tuning message for, in decimal. Defaults to 127 (0x7F), which means \"all devices\"")
    parser.add_argument("--tuning-bank", metavar="BANK", type=int, action="store", default=0, help="Bank ID to store the message for, in decimal. Defaults to 0 under the assumption that it's the current bank for most synths." +\
                                                                                                   " Note that using any non-current bank requires sending bank select commans.")                                                                                               
    parser.add_argument("--pretty-print", action="store_true", help="Formatted output, but more difficult to copy-paste or pipe to a file")
    parser.add_argument("--tuning-range", action="store", type=int, nargs=2, help="Range of notes to tune, exactly two or no numbers separated by space. Default: maximum MIDI range of 0 to 127.")
    parser.add_argument("--notes-per-message", action="store", type=int, default=127, help="Maximum number of notes per message. If tuning range exceeds it, message is split into several. Defaults to MIDI maximum 127.")
    parser.add_argument("--bytes-per-message", action="store", type=int, help="Maximum number of bytes per message. If tuning range exceeds it, message is split into several. Overrides --notes-per-message.")

    

    
    args = parser.parse_args()
    
    if args.tuning_range is None:
        tuning_range = [0, 127]
    else:
        (bottom, top) = args.tuning_range
        tuning_range = [int(bottom), int(top)]
        
    if len(tuning_range) > args.notes_per_message:
        raise Exception("Too many notes per message for a given range. Try decreasing.")
    
    notes = rotate_notes(notes, args.starting_note)
    
    scale = [ratio_to_float(step) for step in args.scale]
    

    if not args.input_cents:
        scale = [ratio_to_cents(ratio) for ratio in scale]
        
    
    if args.from_each_other:
        scale = stepwise_from_root(scale)
        
    
    offsets = offsets_from_another_scale(scale, eqtemp12_cents)
    
    
    if args.print_cents:
        print("\n\n")
        for (step, (note, base_cent, scale_cent, (step_offset, cents_offset))) in enumerate(zip(notes, eqtemp12_cents, scale, offsets)):
            if step_offset is None:
                continue
            note_offset = math.copysign((step+step_offset)%len(notes), step_offset)
            base_note = notes[abs(int(note_offset))]
            step_with_offset = step + step_offset
            octave_offset = step_with_offset//len(notes)
            octave2 = base_octave + int(octave_offset)
            print("{step:2d} ({note:2s}{octave:2d}): \t {scale_cent:15.4f}  =  {base_note:2s}{octave2:2d} + {offset:15.4f} cents".format(step=(step+1),     note=note, octave=base_octave, scale_cent=scale_cent, base_note=base_note, octave2=octave2, offset=cents_offset)     )
        print("\n\n")
    
    if args.bytes_per_message is not None:
        args.notes_per_message = (args.bytes_per_message - bytes_header)//bytes_per_note
    
    messages = make_mts_messages_per_note_rt(notes, offsets, midi_reference_note, midi_note_range, args.device_id, args.tuning_bank, tuning_range, notes_per_message=args.notes_per_message)
    if args.pretty_print:
        printable = hex_print_mts_messages(messages, pretty_print=True, message_type="per_note_rt", delimiter="\n")
        print("\n")
    else:
         printable = hex_print_mts_messages(messages, pretty_print=False, message_type="per_note_rt", delimiter=" ")

    print(printable)
    
    if args.pretty_print:
        print("\n")
    
    
def ratio_to_float(strrat):
    nden = strrat.replace("/", ":").split(":")
    if nden[0] == "x":
        return None
    elif len(nden) == 1:
        res = float(nden[0])
        return res
    elif len(nden) == 2:
        num, denom = nden
        res = float(num)/float(denom)
        return res

    else:
        raise Exception("%s is not a valid number or ratio" % strrat)



def ratio_to_cents(ratio):
    if ratio is not None:
        res = 1200 * math.log(ratio, 2)
    else:
        res = None
    return res



def stepwise_from_root(scale):
    """Convert a scale containing cents
    between each subsequent step into
    cents from root."""
    new_scale = [scale[0]]
    for note in scale[1:]:
        if note is not None:
            new_scale.append(new_scale[-1]+note)
        else:
            new_scape.append(None)
    return new_scale



def offsets_from_another_scale(scale, base_scale):
    """Compute differences between the scale of
    interest and another scale (12 tone equal temperaments for MIDI).
    If a given offset is negative,
    computes distance to a previous scale. Returns a list
    of pairs (whole semitone offset, cents offset).
    Assumes that an octave is a 2:1 ratio expressed as 1200 cents,
    and it wraps around.
    """
    offsets = []
    for (cur_step, (cur_note, cur_base)) in enumerate(zip(scale, base_scale)):
        if cur_note is None:
            offsets.append( (None, None))
            continue
        cents_offset = cur_note - cur_base
        steps_offset = 0
        while not (0 <= cents_offset < midi_max_cents_offset):
            sign = int(math.copysign(1, cents_offset))
            cur_step += sign
            steps_offset += sign
            if not (0 <= cur_step < len(base_scale)):
                cur_step -= sign*len(base_scale)
                cur_note -= sign*cents_in_octave
            cents_offset = cur_note - base_scale[cur_step]
        offsets.append( (steps_offset, cents_offset) )
        
    return offsets




def rotate_notes(notes, starting_note):
    i = notes.index(starting_note.upper())
    notes = notes[i:] + notes[:i]
    return notes



    

def make_mts_tuple(note_id, step_offset, cents_offset):
    """F0 7F = universal realtime SysEx header
       id    = target device ID
       08    = sub-id #1 (MIDI tuning standard)
       02    = sub-id #2 (note change)
       tt    = tuning program number from 0 to 127
       ll    = number of notes to be changed (sets of [kk xx yy zz])
            [kk xx yy zz] = MIDI note number, followed by frequency data for note
            
       F7    = end of SysEx message
       Frequency data format (all bytes in hex)
        xx = semitone (MIDI note number to retune to, unit is 100 cents)               (7 bits, 0xxxxxxx)
        yy = MSB of fractional part (1/128 semitone = 100/128 cents = .78125 cent units)  (7 bits, 0-127, 0xxxxxxx)
        zz = LSB of fractional part (1/16384 semitone = 100/16384 cents = .0061 cent units) (7 bits, 0-127, 0xxxxxxx), 14 bits total for cents

       7F 7F 7F is reserved for no change to the existing note tuning
    """
    semitone = int(note_id + step_offset)
    if not (midi_note_range[0] <= semitone <= midi_note_range[1]):
        raise Exception("semitone not in range")
    
    if not (0 <= cents_offset < midi_max_cents_offset):
        raise Exception("cents offset not in range")
    
    cents_to_midi_ratio = (2**7) / midi_max_cents_offset
    midi_offset = cents_offset * cents_to_midi_ratio
    
    msb = math.floor(midi_offset)
    lsb = round((midi_offset - msb)*(2**7))
    
    if not functools.reduce(lambda acc, cur: acc and (0 <= cur <= 0x7F), [semitone, msb, lsb], True):
        raise Exception("internal error: tuning offset data exceeded maximum MIDI value")
    
    return (semitone, msb, lsb)
    

def make_mts_messages_per_note_rt(notes, offsets, midi_reference_note, midi_note_range, device_id=0x7F, tuning_program=0, tuning_range=[1,127], notes_per_message=0x7F):
    """F0 7F = universal realtime SysEx header
       id    = target device ID
       08    = sub-id #1 (MIDI tuning standard)
       02    = sub-id #2 (note change)
       tt    = tuning program number from 0 to 127
       ll    = number of notes to be changed (sets of [kk xx yy zz])
            [kk xx yy zz] = MIDI note number, followed by frequency data for note
       F7    = end of SysEx message
       
       Frequency data format (all bytes in hex)
        xx = semitone (MIDI note number to retune to, unit is 100 cents)               (7 bits, 0xxxxxxx)
        yy = MSB of fractional part (1/128 semitone = 100/128 cents = .78125 cent units)  (7 bits, 0-127, 0xxxxxxx)
        zz = LSB of fractional part (1/16384 semitone = 100/16384 cents = .0061 cent units) (7 bits, 0-127, 0xxxxxxx), 14 bits total for cents

       7F 7F 7F is reserved for no change to the existing note tuning
    """
    
    ref_note_id = midi_reference_note["ID"] + notes.index(midi_reference_note["note"])
    starting_step = ref_note_id % len(notes)
    
    tuning_tuples = []
    for note_id in range(tuning_range[0], tuning_range[1]+1):  #ditry hack, and it doesn't retune note 0: 8.1758 Hz (C), but we'll be fine
        step_offset, cents_offset = offsets[(note_id + starting_step)%len(notes)]
        if step_offset is None:
            continue
        try:
            semitone, msb, lsb = make_mts_tuple(note_id, step_offset, cents_offset)
            tuning_tuples.append((note_id, semitone, msb, lsb))
        except Exception as e:
            continue

    if len(tuning_tuples) > 0x7F:
        raise Exception("Too many notes to tune in one message.")
        
    messages = []
    buffer = []

    while tuning_tuples:
        buffer, tuning_tuples = tuning_tuples[:notes_per_message], tuning_tuples[notes_per_message:]
    
        message = []
        message.append((0xF0, 0x7F))    #header, real-time SysEx
        message.append(device_id) 
        message.append((0x08, 0x02))    #MTS note change in single note format
        message.append(tuning_program)
        message.append(len(buffer))
        message.append(buffer)
        message.append(0xF7)            #EOM
        
        messages.append(message)
        
    
    return messages


def to_hex(number):
    return " ".join(textwrap.wrap(["0"*(len(stnum)%2) + stnum.upper() for stnum in hex(number).split("0x")][-1], 2))



def hex_print_mts_messages(messages, pretty_print=True, message_type="per_note_rt", delimiter="\n"):
    res = []
    if message_type == "per_note_rt":
        if pretty_print or not pretty_print:
            for message in messages:
                _res = []
                _res.append(" ".join(map(to_hex, message[0])))
                _res.append(to_hex(message[1]))
                _res.append(" ".join(map(to_hex, message[2])))
                _res.append(to_hex(message[3]))
                _res.append(to_hex(message[4]))
                _res.append(   delimiter.join(  map(lambda row: " ".join(map(to_hex, row))  , message[5])   )  )
                _res.append(to_hex(message[6]))
                res.append(delimiter.join(_res))
            
    return "\n\n".join(res)


if __name__ == "__main__":
    main()
    