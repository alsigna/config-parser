from __future__ import annotations
from os import remove
import re


class ConfigTree:
    def __init__(
        self,
        config_line: str = "",
        config_file: str = None,
        config_text: str = None,
        template_file: str = None,
        parent: ConfigTree = None,
        priority: int = 100,
    ) -> None:
        self.parent = parent
        self.child = []
        self.attr = self.get_attr(config_line)
        self.config_line = config_line
        self.priority = priority
        self.skip_line = ["!", "end", "exit-address-family"]
        self.action = ""
        if parent is not None:
            parent.child.append(self)
        if config_file is not None:
            with open(config_file, "r") as file_:
                config_lines = file_.read().strip()
            self.build_tree(config_lines)
        if config_text is not None:
            self.build_tree(config_text)
        if template_file is not None:
            with open(template_file, "r") as file_:
                template_text = file_.read().strip()
            self.assigne_template(ConfigTree(config_text=template_text))

    def __str__(self: ConfigTree) -> str:
        return self.format_config_line(mode="full")

    def __repr__(self: ConfigTree) -> str:
        line = self.format_config_line(mode="full")
        return f"({id(self)}) {line}"

    def build_tree(self: ConfigTree, config_lines: str) -> None:
        sections = re.split(r"\n(?=\S)", config_lines)
        for section in sections:
            self.build_sub_tree(section, self)

    def build_sub_tree(self: ConfigTree, section: str, parent: ConfigTree) -> None:
        lines = section.split("\n")
        if len(lines) == 0:
            return
        if lines[0] in self.skip_line:
            return
        child = ConfigTree(config_line=lines[0].strip(), parent=parent, priority=self.priority)
        if len(lines) == 1:
            return
        sub_lines = []
        spaces = re.match(r"^(\s+)", lines[1]).group(1)
        for line in lines[1:]:
            line_to_add = re.sub(fr"^{spaces}", "", line)
            if line_to_add:
                sub_lines.append(line_to_add)
        sub_section = "\n".join(sub_lines)
        child.build_tree(sub_section)

    def format_config_line(self: ConfigTree, mode: str = "") -> str:
        if (
            "{" not in self.config_line
            and "}" not in self.config_line
            and "[" not in self.config_line
            and "]" not in self.config_line
        ):
            return self.config_line or "root"
        ccb = "<ClosingCurlyBracket>"
        ocb = "<OpeningCurlyBracket>"
        dccb = "<DoubleClosingCurlyBracket>"
        docb = "<DoubleOpeningCurlyBracket>"
        csb = "<ClosingSquareBracket>"
        osb = "<OpeningSquareBracket>"

        cmd = re.sub(r"{{ (\S+) }}", rf"{docb}\1{dccb}", self.config_line)
        cmd = re.sub(r"\{", ocb, cmd)
        cmd = re.sub(r"\}", ccb, cmd)
        cmd = re.sub(r"\[", osb, cmd)
        cmd = re.sub(r"\]", csb, cmd)
        if mode == "re":
            cmd = re.sub(dccb, "}", cmd)
            cmd = re.sub(docb, "{", cmd)
            return cmd
        elif mode == "full":
            cmd = re.sub(dccb, "}", cmd)
            cmd = re.sub(docb, "{", cmd)
            cmd = cmd.format(**self.attr)
            cmd = re.sub(ccb, "}", cmd)
            cmd = re.sub(ocb, "{", cmd)
            cmd = re.sub(csb, "]", cmd)
            cmd = re.sub(osb, "[", cmd)
            return cmd
        else:
            return cmd

    def exists_in(
        self: ConfigTree,
        obj: ConfigTree,
        param: bool = True,
        templ: bool = True,
        bidir: bool = False,
    ) -> bool:
        for indx, obj_child in enumerate(obj.child):
            result = obj_child.eq(self, param=param, templ=templ, bidir=bidir)
            if result:
                return indx, True
        return None, False

    def assigne_template(self: ConfigTree, obj: ConfigTree) -> None:
        for self_child in self.child:
            indx, match = self_child.exists_in(obj, bidir=True)
            if match:
                self_child.attr = obj.child[indx].attr.copy()
                self_child.parse_attr(obj.child[indx].format_config_line(mode="re"))
                self_child.config_line = obj.child[indx].config_line
                self_child.assigne_template(obj.child[indx])
                obj.child.pop(indx)

    def parse_attr(self: ConfigTree, template: str) -> None:
        re_attr = {}
        for attr in self.attr.keys():
            re_attr.setdefault(attr, r"\S+")
        for attr in re_attr:
            re_attr_copy = re_attr.copy()
            re_attr_copy[attr] = r"(\S+)"
            self.attr[attr] = re.findall(rf"^{template.format(**re_attr_copy)}", self.config_line)[0]

    def get_attr(self: ConfigTree, config_line: str) -> dict:
        attr_dict = {}
        attr_list = re.findall(r"{{ \S+ }}", config_line)
        for attr in attr_list:
            attr_dict.setdefault(attr[2:-2].strip(), attr)
        return attr_dict

    def eq(
        self: ConfigTree,
        obj: ConfigTree,
        param: bool = False,
        templ: bool = True,
        bidir: bool = False,
        section: bool = False,
    ) -> bool:
        if section:
            if len(self.child) != len(obj.child):
                return False
            for obj_child in obj.child:
                indx, match = obj_child.exists_in(self, param, templ, bidir)
                if not match:
                    return False
                else:
                    if not obj_child.eq(self.child[indx], param, templ, bidir, section):
                        return False
            return obj.eq(self, param, templ, bidir)
        if str(self) == str(obj):
            if len(self.attr) != 0 and len(obj.attr) != 0:
                if self.config_line == obj.config_line:
                    return True
                else:
                    return False
            else:
                return True
        if not templ:
            return False

        if bidir:
            attr_obj = obj.attr.copy()
            str_obj = obj.format_config_line(mode="re")
            for attr_name, attr_value in attr_obj.items():
                if not param or re.search(r"{{ \S+ }}", attr_value):
                    attr_obj[attr_name] = r"\S+"
            match_result_obj = re.match(rf"^{str_obj.format(**attr_obj)}$", str(self).strip())
        else:
            match_result_obj = None

        attr_self = self.attr.copy()
        str_self = self.format_config_line(mode="re")
        for attr_name, attr_value in attr_self.items():
            if not param or re.search(r"{{ \S+ }}", attr_value):
                attr_self[attr_name] = r"\S+"
        # print(f"{str_self.format(**attr_self)} - {str(obj).strip()}")
        match_result_self = re.match(rf"^{str_self.format(**attr_self)}$", str(obj).strip())

        if match_result_self or match_result_obj:
            if len(self.attr) != 0 and len(obj.attr) != 0:
                if self.config_line == obj.config_line:
                    return True
                else:
                    return False
            else:
                return True

        return False

    def config(self: ConfigTree, symbol: str = " ", symbol_count: int = -1, raw: bool = False) -> str:
        if self.parent is None:
            config_list = []
        else:
            if raw:
                params = " |> " + str(self.attr) if len(self.attr) else ""
                config_list = [self.action + symbol * symbol_count + self.config_line + params]
            else:
                config_list = [self.action + symbol * symbol_count + str(self)]
        for child in self.child:
            config_list.append(child.config(symbol, symbol_count + 1, raw))
        return "\n".join(config_list)

    def copy(self: ConfigTree, with_child: bool = True, parent: ConfigTree = None) -> ConfigTree:
        root = self.__copy(with_child=with_child, parent=parent)
        while root.parent is not None:
            root = root.parent
        return root

    def __copy(self: ConfigTree, with_child: bool, parent: ConfigTree) -> ConfigTree:
        if self.parent is not None and parent is None:
            parent = self.parent.__copy(with_child=False, parent=None)
        new_obj = ConfigTree(
            config_line=self.config_line,
            parent=parent,
            priority=self.priority,
        )
        new_obj.attr = self.attr.copy()
        if not with_child:
            return new_obj
        for child in self.child:
            _ = child.__copy(with_child=with_child, parent=new_obj)
        return new_obj

    def merge(
        self: ConfigTree,
        obj: ConfigTree,
        param: bool = False,
        templ: bool = True,
        bidir: bool = False,
    ) -> None:
        if (
            self.eq(obj, param, templ, bidir)
            and len(self.child) == 0
            and len(obj.child) == 0
            and self.priority < obj.priority
        ):
            if not obj.attr:
                obj.attr = self.attr.copy()
                obj.parse_attr(self.format_config_line(mode="re"))
                obj.config_line = self.config_line
            self.config_line = obj.config_line
            self.attr = obj.attr.copy()
            self.priority = obj.priority
            self.action = obj.action

        for obj_child in obj.child:
            indx, match = obj_child.exists_in(self, param, templ, bidir)
            if not match:
                self.child.append(obj_child)
                obj_child.parent = self
            else:
                self.child[indx].merge(obj_child, param, templ, bidir)

    def replace(
        self: ConfigTree,
        obj: ConfigTree,
        param: bool = True,
        templ: bool = True,
        bidir: bool = False,
    ) -> None:
        for obj_child in obj.child:
            indx, match = obj_child.exists_in(self, param, templ, bidir)
            if match:
                self.child[indx].parent = None
                self.child.pop(indx)
                new_obj = obj_child.__copy(with_child=True, parent=None)
                new_obj.parent = self
                self.child.insert(indx, new_obj)

    def __filter(self: ConfigTree, string: str, with_child: bool, raw: bool) -> list:
        result = []
        for child in self.child:
            if raw:
                r = re.search(rf"{string.strip()}", str(child.config_line).strip())
            else:
                r = re.search(rf"{string.strip()}", str(child).strip())
            if r:
                result.append(child.copy(with_child=with_child))
            if len(child.child) != 0 and (not r or with_child):
                result.extend(child.__filter(string, with_child, raw))
        return result

    def filter(self: ConfigTree, string: str, with_child: bool = True, raw: bool = False) -> ConfigTree:
        root = ConfigTree(priority=self.priority)
        filter_result = []
        filter_result.extend(self.__filter(string, with_child, raw))
        for child in filter_result:
            root.merge(child)
        return root

    def delete(
        self: ConfigTree,
        obj: ConfigTree,
        param: bool = True,
        templ: bool = True,
        bidir: bool = False,
    ) -> None:
        for obj_child in obj.child:
            indx, match = obj_child.exists_in(self, param, templ, bidir)
            if match:
                if len(obj_child.child) != 0:
                    self.child[indx].delete(obj_child)
                if len(self.child[indx].child) == 0 or (len(obj_child.child) == 0 and len(self.child[indx].child) != 0):
                    self.child.pop(indx)
                    obj_child.parent = None

    def __intersection(self: ConfigTree, obj: ConfigTree) -> list:
        result = []
        for obj_child in obj.child:
            indx, match = obj_child.exists_in(self, bidir=True)
            if match:
                if len(obj_child.child) != 0:
                    result.extend(self.child[indx].__intersection(obj_child))

                result.append(self.child[indx].copy(with_child=False))
                self.child.pop(indx)

        return result

    def intersection(self: ConfigTree, obj: ConfigTree) -> ConfigTree:
        inter = ConfigTree(priority=self.priority)
        self_copy = self.copy()
        inter_result = []
        inter_result.extend(self_copy.__intersection(obj))
        for child in inter_result:
            # inter.attach(child)
            inter.merge(child, templ=False)
        return inter

    def difference(self: ConfigTree, obj: ConfigTree) -> ConfigTree:
        self_copy = self.copy()
        inter = self_copy.intersection(obj)
        self_copy.delete(inter)
        return self_copy

    def set_action(self: ConfigTree, action: str = "", section: bool = False) -> None:
        self.action = action
        if section:
            for child in self.child:
                child.set_action(action, section)

    def set_priority(self: ConfigTree, priority: int = 100, section: bool = False) -> None:
        self.priority = priority
        if section:
            for child in self.child:
                child.set_priority(priority, section)

    def __mark_lines_remove(self: ConfigTree, remove_obj: ConfigTree) -> None:
        for self_child in self.child:
            indx, match = self_child.exists_in(remove_obj)
            if match:
                if self_child.eq(remove_obj.child[indx], section=True):
                    self_child.set_action("-", section=True)
                else:
                    self_child.set_action(" ", section=True)
                    self_child.__mark_lines_remove(remove_obj.child[indx])
            else:
                self_child.set_action(" ", section=True)

    def mark_lines(self: ConfigTree, remove_obj: ConfigTree, add_obj: ConfigTree) -> None:
        self.__mark_lines_remove(remove_obj)
        add_obj_copy = add_obj.copy()
        add_obj_copy.set_action("+", section=True)
        add_obj_copy.set_priority(self.priority + 1, section=True)
        self.merge(add_obj_copy, param=True)

    def compliance(self: ConfigTree, obj: ConfigTree) -> tuple:
        intersection = obj.intersection(self)
        add_to_self = obj.difference(self)
        remove_from_self = self.difference(obj)
        full = self.copy()
        full.mark_lines(remove_from_self, add_to_self)
        return intersection, add_to_self, remove_from_self, full


# cfg1 = ConfigTree(
#     config_file="cfg1.txt",
#     # config_file="full.txt",
#     # template_file="cfg1.j2",
#     # priority=103,
# )
# cfg2 = ConfigTree(
#     config_file="cfg2.txt",
#     # template_file="cfg2.j2",
#     priority=101,
# )


# print("~" * 20 + "cfg1")
# print(cfg1.config(raw=True))
# print("~" * 20 + "cfg2")
# print(cfg2.config(raw=True))

# print("~" * 20 + "merge")
# cfg1.merge(cfg2)
# print(cfg1.config(raw=True))

# print("~" * 20 + "replace")
# cfg1.replace(cfg2)
# print(cfg1.config(raw=True))

# print("~" * 20 + "filter")
# fltr = cfg1.filter("ip add 2", with_child=False)
# print(fltr.config(raw=True))

# print("~" * 20 + "delete")
# cfg1.delete(fltr)
# print(cfg1.config(raw=True))

# print("~" * 20 + "section")
# print(cfg1.child[0].eq(cfg2.child[0], section=True))


cfg3 = ConfigTree(
    config_file="cfg1.txt",
    # config_file="full_config.txt",
    # template_file="cfg1.j2",
)
tmpl = ConfigTree(
    config_file="cfg2.j2",
    # config_file="full_config.j2",
    # template_file="cfg2.j2",
)
# dual_hub = ConfigTree(
#     config_file="dual_hub.j2",
#     # config_file="dual_hub.j2",
# )

# print("~" * 20 + "cfg3")
# print(cfg3.config(raw=True))

# print("~" * 20 + "tmpl")
# print(tmpl.config(raw=True))

# print("~" * 20 + "intersection")
# intersection = cfg3.intersection(tmpl)
# print(intersection.config(raw=True))
# # tmpl.merge(dual_hub)

intersection, add, rem, full = cfg3.compliance(tmpl)
print("~" * 20 + "tmpl.intersection(cfg3)")
print(intersection.config(raw=True))
print("~" * 20 + "diff template from config (need to add to config)")
print(add.config(raw=True))
print("~" * 20 + "diff config from template (need to delete from config)")
print(rem.config(raw=True))
print("~" * 20 + "full config")
print(full.config(raw=True))
