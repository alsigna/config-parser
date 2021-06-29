import re


class ConfigTree:
    def __init__(self, line="", parent=None, priority=100) -> None:
        self.parent = parent
        self.child = []
        self.attr = self.get_attr(line)
        self.config_line = line
        self.priority = priority
        self.skip_line = [
            "!",
            "exit-address-family",
        ]
        if parent is not None:
            parent.child.append(self)

    def decode_to_string(self) -> str:
        ccb = "<ClosingCurlyBracket>"
        ocb = "<OpeningCurlyBracket>"
        dccb = "<DoubleClosingCurlyBracket>"
        docb = "<DoubleOpeningCurlyBracket>"
        cmd = self.format_command()
        cmd = re.sub(dccb, "}", cmd)
        cmd = re.sub(docb, "{", cmd)
        cmd = cmd.format(**self.attr) or "root"
        cmd = re.sub(ccb, "}", cmd)
        cmd = re.sub(ocb, "{", cmd)
        return cmd

    def __str__(self) -> str:
        # re_str = self.format_command()
        # return re_str.format(**self.attr) or "root"
        cmd = self.decode_to_string()
        return cmd

    def __repr__(self) -> str:
        cmd = self.decode_to_string()
        return f"({id(self)}) {cmd}"
        # re_str = self.format_command()
        # repr_ = re_str.format(**self.attr) or "root"
        # return f"({id(self)}) {repr_}"
        # return f"({id(self)}) {re_str.format(**self.attr)}" or f"({id(self)})root"

    def __eq__(self, compare_obj: object) -> bool:
        re_attr_1 = {}
        re_attr_2 = {}

        for attr in self.attr.keys():
            re_attr_1.setdefault(attr, r"\S+")
        for attr in compare_obj.attr.keys():
            re_attr_2.setdefault(attr, r"\S+")

        re_str_1 = self.format_command()
        re_str_2 = compare_obj.format_command()

        match_result_1 = re.match(rf"^{re_str_1.format(**re_attr_1)}$", str(compare_obj).strip())
        match_result_2 = re.match(rf"^{re_str_2.format(**re_attr_2)}$", str(self).strip())

        if match_result_1 or match_result_2:
            return True
        else:
            return False

    def format_command(self) -> str:
        if "{" not in self.config_line and "}" not in self.config_line:
            return self.config_line
        ccb = "<ClosingCurlyBracket>"
        ocb = "<OpeningCurlyBracket>"
        dccb = "<DoubleClosingCurlyBracket>"
        docb = "<DoubleOpeningCurlyBracket>"
        cmd = re.sub(r"{{ (\S+) }}", rf"{docb}\1{dccb}", self.config_line)
        cmd = re.sub(r"{", ocb, cmd)
        cmd = re.sub(r"}", ccb, cmd)
        # cmd = re.sub(dccb, "}", cmd)
        # cmd = re.sub(docb, "{", cmd)
        return cmd
        # cmd = re.sub(r"{{ ", "{", self.config_line)
        # cmd = re.sub(r" }}", "}", cmd)
        # return cmd

    def get_attr(self, cmd) -> dict:
        attr_dict = {}
        attr_list = re.findall(r"{{ \S+ }}", cmd)
        for attr in attr_list:
            attr_dict.setdefault(attr[2:-2].strip(), attr)
        return attr_dict

    def get_config(self, symbol=" ", symbol_count=-1, raw=False) -> str:
        if self.parent is None:
            config_list = []
        else:
            if raw:
                config_list = [symbol * symbol_count + self.config_line]
            else:
                config_list = [symbol * symbol_count + str(self)]
        for child in self.child:
            config_list.append(child.get_config(symbol, symbol_count + 1, raw))
        return "\n".join(config_list)

    def build_tree(self, config, lvl=""):
        sections = re.split(r"\n(?=\S)", config)
        for section in sections:
            self.build_sub_tree(section, lvl, self)

    def build_sub_tree(self, section, lvl, leaf):
        lines = section.split("\n")
        if len(lines) == 1:
            if lines[0] not in self.skip_line:
                ConfigTree(line=section.strip(), parent=leaf, priority=self.priority)
        else:
            sub_leaf = ConfigTree(line=lines[0].strip(), parent=leaf, priority=self.priority)
            sub_lines = []
            spaces = re.match(r"^(\s+)", lines[1])
            for line in lines[1:]:
                line_to_add = re.sub(fr"^{spaces.group(1)}", "", line)
                if line_to_add:
                    sub_lines.append(line_to_add)
            sub_section = "\n".join(sub_lines)
            sub_leaf.build_tree(sub_section, lvl + lines[0].strip() + " ")

    def full_path(self):
        if self.parent is not None:
            parent = ConfigTree(priority=self.priority)
            parent.attr = self.parent.attr
            parent.config_line = self.parent.config_line
            parent.child.append(self)
            parent.parent = self.parent.parent
            self.parent = parent
            return parent.full_path()
        else:
            return self

    def merge(self, obj):
        if self == obj and len(self.child) == 0 and len(obj.child) == 0 and self.priority < obj.priority:
            self.attr = obj.attr

        for obj_child in obj.child:
            if obj_child not in self.child:
                self.child.append(obj_child)
                obj_child.parent = self
            else:
                for self_child in self.child:
                    if self_child == obj_child:
                        self_child.merge(obj_child)

    def parse_attr(self, template):
        re_attr = {}
        for attr in self.attr.keys():
            re_attr.setdefault(attr, r"\S+")
        for attr in re_attr:
            re_attr_copy = re_attr.copy()
            re_attr_copy[attr] = r"(\S+)"
            self.attr[attr] = re.findall(rf"^{template.format(**re_attr_copy)}", self.config_line)[0]

    def add_template(self, template):
        for template_child in template.child:
            for self_child in self.child:
                if self_child == template_child:
                    self_child.attr = template_child.attr
                    self_child.parse_attr(template_child.format_command())
                    self_child.config_line = template_child.config_line
                    self_child.add_template(template_child)

    def __filter(self, string):
        result = []
        for child in self.child:
            r = re.search(rf"{string.strip()}", str(child).strip())
            if r:
                result.append(child)
            if len(child.child) != 0:
                result.extend(child.__filter(string))
        return result

    def filter(self, string):
        root = ConfigTree()
        filter_result = []
        filter_result.extend(self.__filter(string))
        for child in filter_result:
            child_full = child.full_path()
            root.merge(child_full)

        return root


def get_tree(filename, template=None, priority=100):
    with open(filename, "r") as file:
        cfg_lines = file.read().strip()
    cfg = ConfigTree(priority=priority)
    cfg.build_tree(cfg_lines)
    if template is not None:
        with open(template, "r") as file:
            tmpl_lines = file.read().strip()
        tmpl = ConfigTree()
        tmpl.build_tree(tmpl_lines)
        cfg.add_template(tmpl)
    return cfg


template = get_tree("cfg.j2")
# print("~" * 20 + "template" + "~" * 20)
# print(template.get_config())

# cfg1 = get_tree("cfg1.txt")
# print("~" * 20 + "config" + "~" * 20)
# print(cfg1.get_config())
# print("~" * 20 + "templated config" + "~" * 20)
# cfg1.add_template(template)
# print(cfg1.get_config(raw=True))

print("~" * 20 + "merged" + "~" * 20)
cfg1 = get_tree("cfg1.txt", "cfg.j2")
cfg2 = get_tree("cfg2.txt", "cfg.j2", 101)
cfg1.merge(cfg2)
print(cfg1.get_config())

# print("~" * 20 + "filter" + "~" * 20)
# f = cfg1.filter("activate")
# # f = cfg1.filter("^interface V\S+0")
# print(f.get_config())

# print("~" * 50)
# full = get_tree("full.txt")
# print(full.get_config())

# print(cfg1.child[0] == cfg2.child[0])

# print(root.child)
# print("~" * 50)
# print(root.get_config(symbol=" "))
# print("~" * 50)
# l = root.child[5].child[7].child[2]
# root_l = l.full_path()
# print(root_l.get_config())
# print("~" * 50)
# vlan10 = root.child[0].full_path()
# vlan11 = root.child[1].full_path()
# print(vlan10.get_config())
# print(vlan11.get_config())
# print("~" * 50)
# vlan10.merge(vlan11)
# print(vlan10.get_config())

# print("~" * 50)
# comm = root.child[5].child[7].child[2].full_path()
# redi = root.child[5].child[8].child[0].full_path()
# comm.merge(redi)
# print(comm.get_config())

# print("~" * 50)
# comm = root.child[0].child[0].full_path()
# redi = root.child[1].child[0].full_path()
# comm.merge(redi)
# print(comm.get_config())
