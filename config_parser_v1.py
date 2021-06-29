import re
from sre_constants import SRE_FLAG_ASCII

# from pprint import pprint as print


class ConfigTree:
    def __init__(self, line="", parent=None) -> None:
        self.parent = parent
        self.child = []
        self.attr = self.get_attr(line)
        self.config_line = self.format_command(line)
        if parent is not None:
            parent.child.append(self)

    def __str__(self) -> str:
        return self.config_line.format(**self.attr)

    def __repr__(self) -> str:
        return self.config_line.format(**self.attr)

    def __eq__(self, compare_obj: object) -> bool:
        re_attr_1 = {}
        re_attr_2 = {}

        for attr in self.attr.keys():
            re_attr_1.setdefault(attr, r"\S+")
        for attr in compare_obj.attr.keys():
            re_attr_2.setdefault(attr, r"\S+")

        match_result_1 = re.match(rf"^{self.config_line.format(**re_attr_1)}$", str(compare_obj).strip())
        match_result_2 = re.match(rf"^{compare_obj.config_line.format(**re_attr_2)}$", str(self).strip())

        if match_result_1 or match_result_2:
            return True
        else:
            return False

    def format_command(self, cmd) -> str:
        cmd = re.sub(r"{{ ", "{", cmd)
        cmd = re.sub(r" }}", "}", cmd)
        return cmd

    def get_attr(self, cmd) -> dict:
        attr_dict = {}
        attr_list = re.findall(r"{{ \S+ }}", cmd)
        for attr in attr_list:
            attr_dict.setdefault(attr[2:-2].strip(), attr)
        return attr_dict

    def get_config(self, space="") -> str:
        config_list = [space + str(self)]
        for child in self.child:
            add_space = "  " if self.parent is not None else ""
            config_list.append(child.get_config(space + add_space))
        return "\n".join(config_list)

    def copy(self, source):
        self.child = source.child
        self.attr = source.attr
        self.config_line = source.config_line

    def add_child(self, child):
        self.child.append(child)
        child.parent = self

    def attach(self, obj):
        if obj.parent is None:
            self.child.append(obj)

    def get_full_path(self):
        root = ConfigTree()
        root.attach(self)
        return root

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
        filtered_list = self.__filter(string)
        for child in filtered_list:
            pass

        # root = ConfigTree(parent=parent)
        # for child in self.child:
        #     match_result = re.match(rf"{string.strip()}", str(child).strip())
        #     if match_result:
        #         copy_child = ConfigTree()
        #         copy_child.copy(child)
        #         copy_child.parent = root
        #         root.child.append(copy_child)
        #     if len(child.child) != 0:
        #         f = child.filter(string, root)
        # return root

    def compliance(self, target):
        if self != target:
            print(f"{str(self)} = net")
        else:
            print(f"{str(self)} = da")
            if len(self.child) != 0:
                for child in self.child:
                    if child not in target.child:
                        print(f"{str(child)} = net")
                    else:
                        # print(f"{str(child)} = da")
                        child.compliance(target.child.pop(target.child.index(child)))

    def compliance2(self, target):
        for indx_self, child_self in enumerate(self.child):
            for indx_target, child_target in enumerate(target.child):
                if child_self == child_target:
                    child_self.compliance2(target.child.pop(indx_target))
        if self == target:
            print(f"{str(self)} = da")
        else:
            print(f"{str(self)} = net")


with open("test1.j2", "r") as file:
    lines = file.read().strip()

# lines = lines.strip()
# print(lines)

skip_cmd = ["!", "exit-address-family"]


def formal_config(section, lvl="", leaf=None):
    lines = section.split("\n")
    if len(lines) == 1:
        if lines[0] in skip_cmd:
            return []
        else:
            ConfigTree(line=section.strip(), parent=leaf)
            return [lvl + section.strip()]
    else:
        sub_leaf = ConfigTree(line=lines[0].strip(), parent=leaf)
        result = [lvl + lines[0].strip()]
        sub_lines = []
        spaces = re.match(r"^(\s+)", lines[1])
        for line in lines[1:]:
            sub_lines.append(re.sub(fr"^{spaces.group(1)}", "", line))
        sub_section = "\n".join(sub_lines)
        result.extend(split_sections(sub_section, lvl + lines[0].strip() + " ", leaf=sub_leaf))
    return result


def split_sections(config, lvl="", leaf=None):
    result = []
    sections = re.split(r"\n(?=\S)", config)
    for s in sections:
        result.extend(formal_config(s, lvl, leaf))
    return result


# lines = re.sub(r"!\n\s*", "", lines)

# print(lines)
# sections = re.split(r"\n(?=\S)", lines)

# print(sections[0])
# for s in sections:
#     print(s.split("\n"))
#     print("~" * 50)

root = ConfigTree()
list_ = split_sections(lines, leaf=root)

for l in list_:
    print(l)


print(root.child)
print("~" * 50)
print(root.get_config())
print("~" * 50)

target_config = """interface Vlan10
 load-interval 40
 no shutdown
 new line
!
ip forward-protocol nf
no ip http secure-server
!"""
target = ConfigTree()
print(target.get_config())
split_sections(target_config, leaf=target)


# print("~" * 50)
print(root.child[1].child[1].get_config())
print(root.child[1].child[1].get_full_path())
# print(target.child[1].get_config())

print("~=" * 50)
# print(target.compliance2(root))
# f = root.filter(r"interface Vlan")
# print(f)
# for i in f:
# print(f.get_config())
# print(root.filter(r"interface \S+0$"))
print("~" * 50)
# print(root.child[0])
# print(root.child[1] in target.child)
# f = root.filter(r"interface")
# for i in f:
#     print(i.get_config())

# print(f)
# print(f.get_config())
print("~" * 50)
