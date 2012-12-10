#!/usr/bin/env python3

# python modules
import re
import collections
import linecache
import subprocess

# my modules
import atoms

class GaussianFile():
    def __init__(self):
        pass

    def read_gaussian_input_structure(self, lines_list):
        atoms_list = []
        for line in lines_list:
            line = line.strip()
            ### check for PDB information
            if '(' in line and ')' in line:
                has_pdb_info = True
                pdb_info = line.split("(")[1].split(")")[0]
                pdb_info_list = pdb_info.split(",")
                line = line.replace("({})".format(pdb_info), "")
                for info in pdb_info_list:
                    if 'PDBName' in info:
                        pdb_atom_name = info.split("=")[1]
                    if 'ResName' in info:
                        pdb_res_name = info.split("=")[1]
                    if 'ResNum' in info:
                        pdb_res_number = info.split("=")[1]
                        if '_' in pdb_res_number : # presence of chain information
                            pdb_res_number, pdb_chain  = info.split("_")
            else:
                pdb_atom_name = pdb_res_name = pdb_res_number = pdb_chain = None
                has_pdb_info = False
            line_list = line.split(None, 5)

            if len(line_list) == 4:
                element, x, y, z = line_list
                this_atom = atoms.Atom(element, x, y, z)
            elif len(line_list) == 6:
                mm_type_charge, mask, x, y, z, layer = line_list[0:6]
                try:
                    element, mm_type, mm_charge = mm_type_charge.split('-',2)
                except ValueError:
                    print("WARNING: Atom no {} does not have all amber info\n".format(len(atoms_list)+1),
                          "        Setting mm_charge to 0 and mm_type to None")
                    element = mm_type_charge.split('-',2)[0]
                    mm_type =  None
                    mm_charge = 0
                if has_pdb_info:
                    this_atom = atoms.QmmmAtomPdb(element, mm_type, mm_charge, mask, x, y, z, layer, pdb_atom_name, pdb_res_name, pdb_res_number)
                else:
                    this_atom = atoms.QmmmAtom(element, mm_type, mm_charge, mask, x, y, z, layer)
            atoms_list.append(this_atom)
        return atoms_list


class EmptyGaussianCom(GaussianFile):
    def __init__(self, name):
        self.name = name
        self.link_0_commands = ["%nproc=8\n", "%mem=6GB\n", "%chk=default.chk\n"]
        self.route_section = "#\n"
        self.title_line = "title line required\n"
        self.multiplicity_line = ""
        self.atoms_list = []
        self.additional_input_dict = {"connect":None, "modred":None, "gen":None,
                                      "pseudo=read":None}
    def write_to_file(self,name):
        with open(name, 'w', encoding='UTF-8') as gaussian_com_file:
            for line in self.link_0_commands:
                gaussian_com_file.write(line)
            gaussian_com_file.write(self.route_section)
            gaussian_com_file.write("\n")   
            gaussian_com_file.write(self.title_line)
            gaussian_com_file.write("\n")
            gaussian_com_file.write(self.multiplicity_line)
            for atom in self.atoms_list:
                # Write the freaking pdb file yeahhhh!
                if type(atom) == atoms.QmmmAtom:
                    atom_type_charge = "{0.element}-{0.mm_type}-{0.charge:.6f}"\
                                        .format(atom)
                    line = ("{0:16s}{1.mask:>2s}{1.x:>14.8f}{1.y:>14.8f}"
                            "{1.z:>14.8f} {1.layer:s}\n"
                            .format(atom_type_charge,atom))
                    gaussian_com_file.write(line)
                else:
                    line = ("{0.element:18s}{0.x:>14.8f}{0.y:>14.8f}"
                    "{0.z:>14.8f}\n".format(atom))
                    gaussian_com_file.write(line)                
            for section in self.additional_input_dict:
                if self.additional_input_dict[section]:
                    gaussian_com_file.write("\n")
                    for line in self.additional_input_dict[section]:
                        gaussian_com_file.write(line)
            gaussian_com_file.write("\n")


class GaussianCom(EmptyGaussianCom):
    def __init__(self, name):
            self.name = name
            self.lines = self._read_lines()
            self.blank_lines = self._count_blank_lines()
            self.link_0_commands = self._read_link_0_commands()
            self.route_section = self._read_route_section()
            self.title_line = self._read_title_line()
            self.multiplicity_line = self._read_multiplicity_line()
            self.atoms_list = self._read_structure()
            self.additional_input_dict = self._read_additional_input()
            self.connectivity_list = self.additional_input_dict["connect"]
            self.modredundant_list = self.additional_input_dict["modred"]
            self.gen_list = self.additional_input_dict["gen"]
            self.pseudo_list = self.additional_input_dict["pseudo=read"]

    def _read_lines(self):
        """Reads lines to a list and strips the \\n"""
        with open(self.name, 'r', encoding='UTF-8') as file:
            lines = file.readlines()
            #lines = [line.strip() for line in lines]
        return lines
            
    def _count_blank_lines(self):
        """Return a list with the blank lines number"""
        blank_lines = []
        for no, line in enumerate(self.lines):
            if line.strip() == '':
                blank_lines.append(no)
        return blank_lines

    def _read_link_0_commands(self):
        """Return a list with Link 0 commands"""
        link_0_commands = []
        for line in self.lines[:self.blank_lines[0]]:
            if '%' in line: link_0_commands.append(line)
        return link_0_commands

    def _read_route_section(self):
        """Return a string with the route section"""
        read_route_section = False
        route_section = ''
        for line in self.lines[:self.blank_lines[0]]:
            if read_route_section:
                route_section += "\n{}".format(line)
            if '#' in line:
                read_route_section = True
                route_section += line
        route_section = route_section
        return route_section

    def _read_title_line(self):
        """Return a string with the title """
        title_line = self.lines[self.blank_lines[0]+1]
        return title_line

    def _read_multiplicity_line(self):
        """Return a string with the multiplicity """
        multiplicity_line = self.lines[self.blank_lines[1]+1]
        return multiplicity_line

    def _read_structure(self):
        """ Return a list of atoms"""
        return self.read_gaussian_input_structure(self.lines[self.blank_lines[1]+2:self.blank_lines[2]])

    def _read_additional_input(self):
        """Reads additional input and stores it in a ordered dict"""
        additional_input_dict = collections.OrderedDict(\
        [("connect",None),("modred",None),("gen",None),("pseudo=read",None)])
        shift = 0
        b_lines = self.blank_lines
        for key in additional_input_dict:
            if key in self.route_section.lower():
                i_start, i_finish = b_lines[2+shift]+1,b_lines[3+shift]
                additional_input_dict[key]= self.lines[i_start: i_finish]
                shift += 1
        return additional_input_dict


class GaussianLog(GaussianFile):
    def __init__(self, name):
        self.name = name
        self.file = open(self.name, 'r')
        self.route_section = self._read_route_section()
        self.amber = "amber" in self.route_section.lower()
        self.opt = "opt" in self.route_section.lower()
        self.energies_list, self.steps_list = self._read_steps_and_energies()
        self.symbolic_zmatrix = self.read_symbolic_zmatrix()
        self.initial_geometry = self.read_geometry(0, 0)
        self.final_geometry = self.read_geometry(-1, -1)
        self.summary = self._generate_summary()

    def _read_route_section(self):
        """ Returns a string with the route section commands"""
        self.file.seek(0)
        reading = False
        for line in self.file:
            if '#' in line:
                route_section = line
                reading = True
            elif reading:
                if'-------' in line:
                    break
                else:
                    route_section += line
        route_section = route_section.strip()
        return route_section
                           
    def _read_steps(self):
        """Creates a two dimensions list with the a tuple corresponding
        to where where the steps start and finish (lines or bytes?)"""
        steps_list = [[]]
        previous_scan_step = scan_step = 0
        start_step_byte = 0
        grep_out = subprocess.check_output("grep -b 'Step number' {}".format(self.name), shell=True)
        grep_out = str(grep_out)[2:-2]
        lines_grep = grep_out.split("\\n")
        for line in lines_grep:
            end_step_byte = int(line.split(":")[0])
            steps_list[scan_step].append((start_step_byte, end_step_byte))
            start_step_byte = end_step_byte
            if "scan point" in line:
                scan_step = int(line.split()[13]) - 1
                if scan_step != previous_scan_step:
                    steps_list.append([])
                    previous_scan_step = scan_step
        steps_list[scan_step].append((start_step_byte, -1)) # last structure
        return steps_list

    def _read_steps_and_energies(self):
        false_steps_list = [[]]
        energies_list = [[0]]
        if self.amber:
            search_str = "extrapolated energy"
        else:
            search_str = "SCF Done"
        previous_scan_step = scan_step = 0
        start_step_byte = 0
        grep_out = subprocess.check_output("grep -b '\(Step number\|{}\)' {}".format(search_str,self.name), shell=True)
        grep_out = str(grep_out)[2:-3]
        lines_grep = grep_out.split("\\n")
        for line in lines_grep:
            if "Step number" in line:
                end_step_byte = int(line.split(":")[0])
                false_steps_list[scan_step].append((start_step_byte, end_step_byte))
                start_step_byte = end_step_byte
                if "scan point" in line:
                    scan_step = int(line.split()[13]) - 1
                    if scan_step != previous_scan_step:
                        false_steps_list.append([])
                        previous_energy= energies_list[-1].pop(-1)
                        energies_list.append([previous_energy])
                        previous_scan_step = scan_step
                false_steps_list[scan_step].append((start_step_byte, -1)) # last structure
                energies_list[-1].append(0)
            if search_str in line:
                energy = float(line.split()[5])
                energies_list[-1][-1] = energy
        energies_list[-1].pop(-1)
        #for single points
        if not self.opt:
            for line in self.file:
                if search_str in line:
                    energy = float(line.split()[4])
                    energies_list = [[energy]]
                    break
        return energies_list, false_steps_list
    
    def read_geometry(self, opt_step, scan_step):
        "Returns a list of atoms with the respective coordinates"
        # lines to read
        if self.opt:
            step_start = self.steps_list[scan_step][opt_step][0]
        else:
            step_start = 0
        self.file.seek(step_start)
        atoms_list = []
        reading = False
        for line in self.file:
            if reading:
                if "-------" in line:
                    break
                else:
                    atomic_number = line.split()[1]
                    x, y, z = line.split()[3:6]
                    element = [key for key in iter(atoms.ATOMIC_NUMBER_DICT) \
                               if atoms.ATOMIC_NUMBER_DICT[key] == int(atomic_number)][0] #hack
                    atoms_list.append(atoms.Atom(element, x, y, z))
            elif " orientation:" in line:
                for _ in range(4): next(self.file)
                reading = True    
        return atoms_list
      
    def read_symbolic_zmatrix(self):
        self.file.seek(0)
        reading = False
        atoms_lines = []
        for no, line in enumerate(self.file):
            if reading:
                if "Charge" in line:
                    pass
                elif line.strip() == '':
                    break
                else:
                    atoms_lines.append(line)
            if "Symbolic Z-matrix:" in line:
                reading = True
        return self.read_gaussian_input_structure(atoms_lines)
    
    def _generate_summary(self):
        no_opts = 0
        for scan_step in self.steps_list:
            no_opts += len(scan_step)
        no_scans = len(self.steps_list) - 1
        energy = self.energies_list[-1][-1]       
        summary = """Reading from {0.name}        
        Route Section:
        {0.route_section}
        
        List of Atoms
        {2} atoms: {1}...
        
        Opt Steps: {3}
        Scan Steps: {4}
        
        Last Energy: {5}
        """.format(self, self.initial_geometry[:100], len(self.initial_geometry), no_opts, no_scans, energy)
        return summary


