from __future__ import annotations
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
        self.skip_line = ["!", "exit-address-family"]
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

    def format_config_line(self: ConfigTree, mode: str = "") -> str:
        if "{" not in self.config_line and "}" not in self.config_line:
            return self.config_line or "root"
        ccb = "<ClosingCurlyBracket>"
        ocb = "<OpeningCurlyBracket>"
        dccb = "<DoubleClosingCurlyBracket>"
        docb = "<DoubleOpeningCurlyBracket>"
        cmd = re.sub(r"{{ (\S+) }}", rf"{docb}\1{dccb}", self.config_line)
        cmd = re.sub(r"{", ocb, cmd)
        cmd = re.sub(r"}", ccb, cmd)
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
            return cmd
        else:
            return cmd

    def parse_attr(self: ConfigTree, template: str) -> None:
        re_attr = {}
        for attr in self.attr.keys():
            re_attr.setdefault(attr, r"\S+")
        for attr in re_attr:
            re_attr_copy = re_attr.copy()
            re_attr_copy[attr] = r"(\S+)"
            self.attr[attr] = re.findall(rf"^{template.format(**re_attr_copy)}", self.config_line)[0]

    def assigne_template(self: ConfigTree, template: ConfigTree) -> None:
        # for template_child in template.child:
        #     for self_child in self.child:
        for self_child in self.child:
            for indx, template_child in enumerate(template.child):
                if self_child == template_child and len(self_child.attr) == 0:
                    self_child.attr = template_child.attr.copy()
                    self_child.parse_attr(template_child.format_config_line(mode="re"))
                    self_child.config_line = template_child.config_line
                    self_child.assigne_template(template_child)
                    template.child.pop(indx)
                    break

    def get_attr(self: ConfigTree, config_line: str) -> dict:
        attr_dict = {}
        attr_list = re.findall(r"{{ \S+ }}", config_line)
        for attr in attr_list:
            attr_dict.setdefault(attr[2:-2].strip(), attr)
        return attr_dict

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

    def __compare__(self: ConfigTree, self_attr: dict, obj: ConfigTree, obj_attr: dict) -> bool:
        re_str_self = self.format_config_line(mode="re")
        re_str_obj = obj.format_config_line(mode="re")

        if re_str_self == re_str_obj:
            return True

        match_result_self = re.match(rf"^{re_str_self.format(**self_attr)}$", str(obj).strip())
        match_result_obj = re.match(rf"^{re_str_obj.format(**obj_attr)}$", str(self).strip())

        if match_result_self or match_result_obj:
            return True
        else:
            return False

    def eq3(self: ConfigTree, obj: ConfigTree) -> bool:
        re_str_self = self.format_config_line(mode="re")
        re_str_obj = obj.format_config_line(mode="re")

        re_attr_self = {}
        re_attr_obj = {}

        for attr in self.attr.keys():
            re_attr_self.setdefault(attr, r"\S+")
        for attr in obj.attr.keys():
            re_attr_obj.setdefault(attr, r"\S+")

        match_result_self = re.match(rf"^{re_str_self.format(**re_attr_self)}$", str(obj).strip())
        match_result_obj = re.match(rf"^{re_str_obj.format(**re_attr_obj)}$", str(self).strip())

        return bool(match_result_self) or bool(match_result_obj)

    def eq2(self: ConfigTree, obj: ConfigTree) -> bool:
        re_str_self = self.format_config_line(mode="re")
        re_str_obj = obj.format_config_line(mode="re")

        str_self = re_str_self.format(**self.attr)
        str_obj = re_str_obj.format(**obj.attr)

        return str_self == str_obj and self.config_line == obj.config_line

    def eq(self: ConfigTree, obj: ConfigTree, strict: bool = False) -> bool:
        re_attr_self = self.attr.copy()
        re_attr_obj = obj.attr.copy()

        if strict:
            return self.__compare__(re_attr_self, obj, re_attr_obj)

        for attr_name, attr_value in re_attr_self.items():
            if re.search(r"{{ \S+ }}", attr_value):
                re_attr_self[attr_name] = r"\S+"
        for attr_name, attr_value in re_attr_obj.items():
            if re.search(r"{{ \S+ }}", attr_value):
                re_attr_obj[attr_name] = r"\S+"

        return self.__compare__(re_attr_self, obj, re_attr_obj)

    def __in_const__(self: ConfigTree, obj: ConfigTree) -> bool:
        if self.config_line == obj.config_line:
            return True
        return False

    def __in_param__(self: ConfigTree, obj: ConfigTree) -> bool:
        if self.eq2(obj):
            return True
        return False

    def __in_templ__(self: ConfigTree, obj: ConfigTree) -> bool:
        if self.eq3(obj):
            return True
        return False

    def exists_in(self: ConfigTree, obj: ConfigTree, mode: str = "const") -> bool:
        for indx, obj_child in enumerate(obj.child):
            if mode == "const":
                result = self.__in_const__(obj_child)
            elif mode == "param":
                result = self.__in_param__(obj_child)
            elif mode == "templ":
                result = self.__in_templ__(obj_child)
            elif mode == "auto":
                if not len(obj_child.attr) and not len(self.attr):
                    result = self.__in_const__(obj_child)
                # elif len(self.attr):
                else:
                    result = self.__in_param__(obj_child)
                # else:
                #     result = False
                # result = self.eq(obj_child)
                # result = self.__in_templ__(obj_child)
            else:
                result = False
            if result:
                return indx, True
        return None, False

    def __eq__(self: ConfigTree, obj: ConfigTree) -> bool:
        re_attr_self = {}
        re_attr_obj = {}

        for attr in self.attr.keys():
            re_attr_self.setdefault(attr, r"\S+")
        for attr in obj.attr.keys():
            re_attr_obj.setdefault(attr, r"\S+")

        return self.__compare__(re_attr_self, obj, re_attr_obj)

    def config(self: ConfigTree, symbol: str = " ", symbol_count: int = -1, raw: bool = False) -> str:
        if self.parent is None:
            config_list = []
        else:
            if raw:
                config_list = [symbol * symbol_count + self.config_line]
            else:
                config_list = [symbol * symbol_count + str(self)]
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

    def replace(self: ConfigTree, obj: ConfigTree) -> None:
        for obj_child in obj.child:
            for indx, self_child in enumerate(self.child):
                if obj_child.eq(self_child) and obj_child.priority > self.priority:
                    self_child.parent = None
                    self.child.pop(indx)
                    new_obj = obj_child.__copy(with_child=True, parent=None)
                    new_obj.parent = self
                    self.child.insert(indx, new_obj)

    # def full_path(self: ConfigTree) -> ConfigTree:
    #     if self.parent is not None:
    #         parent = ConfigTree(priority=self.priority)
    #         parent.attr = self.parent.attr.copy()
    #         parent.config_line = self.parent.config_line
    #         parent.child.append(self)
    #         parent.parent = self.parent.parent
    #         self.parent = parent
    #         return parent.full_path()
    #     else:
    #         return self

    def attach(self: ConfigTree, obj: ConfigTree, mode: str = "") -> None:
        if self.eq3(obj) and len(self.child) == 0 and len(obj.child) == 0 and self.priority < obj.priority:
            if not obj.attr:
                obj.attr = self.attr.copy()
                obj.parse_attr(self.format_config_line(mode="re"))
            self.attr = obj.attr.copy()
            self.config_line = obj.config_line

        for obj_child in obj.child:
            if not mode:
                if obj_child.attr:
                    indx, match = obj_child.exists_in(self, mode="const")
                else:
                    indx, match = obj_child.exists_in(self, mode="templ")
            if not match:
                # if not obj_child.exists_in(self, mode="const"):
                self.child.append(obj_child)
                obj_child.parent = self
            else:
                self.child[indx].attach(obj_child)
                # for self_child in self.child:
                #     if self_child == obj_child:
                #         self_child.merge(obj_child)

    def merge(self: ConfigTree, obj: ConfigTree) -> None:
        if self == obj and len(self.child) == 0 and len(obj.child) == 0 and self.priority < obj.priority:
            obj.attr = self.attr.copy()
            obj.parse_attr(self.format_config_line(mode="re"))
            self.attr = obj.attr.copy()

        for obj_child in obj.child:
            if obj_child not in self.child:
                self.child.append(obj_child)
                obj_child.parent = self
            else:
                for self_child in self.child:
                    if self_child == obj_child:
                        self_child.merge(obj_child)

    def combine(self: ConfigTree, obj: ConfigTree) -> None:
        if self.eq(obj) and len(self.child) == 0 and len(obj.child) == 0:
            obj.attr = self.attr.copy()
            obj.parse_attr(self.format_config_line(mode="re"))
            self.attr = obj.attr.copy()

        for obj_child in obj.child:
            if not obj_child.exists_in(self):
                self.child.append(obj_child)
                obj_child.parent = self
            else:
                for self_child in self.child:
                    if self_child.eq(obj_child):
                        self_child.combine(obj_child)

    def __filter(self: ConfigTree, string: str, with_child: bool) -> list:
        result = []
        for child in self.child:
            r = re.search(rf"{string.strip()}", str(child).strip())
            if r:
                result.append(child.copy(with_child=with_child))
            if len(child.child) != 0 and (not r or with_child):
                result.extend(child.__filter(string, with_child))
        return result

    def filter(self: ConfigTree, string: str, with_child: bool = True) -> ConfigTree:
        root = ConfigTree(priority=self.priority)
        filter_result = []
        filter_result.extend(self.__filter(string, with_child=with_child))
        for child in filter_result:
            root.merge(child)
        return root

    def delete(self: ConfigTree, obj: ConfigTree) -> None:
        # for obj_child in obj.child:
        #     for indx, self_child in enumerate(self.child):
        #         if self_child.eq(obj_child):
        #             if len(obj_child.child) != 0:
        #                 self_child.delete(obj_child)
        #             if len(self_child.child) == 0:
        #                 self_child.parent = None
        #                 self.child.pop(indx)
        # for self_child in self.child:
        for obj_child in obj.child:
            # if obj_child.attr:
            #     indx, match = obj_child.exists_in(self, mode="const")
            # else:
            indx, match = obj_child.exists_in(self, mode="param")
            # if not match:
            #     # if not obj_child.exists_in(self, mode="const"):
            #     self.child.append(obj_child)
            #     obj_child.parent = self
            # else:
            #     self.child[indx].attach(obj_child)
            if match:
                if len(obj_child.child) != 0:
                    # self_child.delete(obj.child[indx])
                    self.child[indx].delete(obj_child)
                # if len(self_child.child) == 0:
                if len(self.child[indx].child) == 0:
                    self.child.pop(indx)
                    obj_child.parent = None

                # if self_child.eq(obj_child):
                #     if len(obj_child.child) != 0:
                #         self_child.delete(obj_child)
                #     if len(self_child.child) == 0:
                #         self_child.parent = None
                #         self.child.pop(indx)

    def __intersection(self: ConfigTree, obj: ConfigTree) -> list:
        result = []
        # for obj_child in obj.child:
        #     for indx, self_child in enumerate(self.child):
        #         if self_child.eq(obj_child):
        #             if len(self_child.child) != 0:
        #                 result.extend(self_child.__intersection(obj_child))

        #             result.append(self_child.copy(with_child=False))
        #             self.child.pop(indx)
        #             break

        # if obj_child.attr:
        #     indx, match = obj_child.exists_in(self, mode="const")
        # else:
        #     indx, match = obj_child.exists_in(self, mode="templ")

        for obj_child in obj.child:
            # if obj_child.attr:
            #     indx, match = obj_child.exists_in(self, mode="templ")
            # else:
            #     indx, match = obj_child.exists_in(self, mode="templ")

            indx, match = obj_child.exists_in(self, mode="auto")
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
            inter.attach(child)
            # inter.merge(child)
        return inter

    def difference(self: ConfigTree, obj: ConfigTree) -> ConfigTree:
        # diff = self.copy()
        # inter = self.intersection(obj)
        # diff.delete(inter)
        # return diff
        self_copy = self.copy()
        # obj_copy = obj.copy()

        inter = self_copy.intersection(obj)
        self_copy.delete(inter)
        return self_copy


# cfg1 = ConfigTree(
#     config_file="cfg1.txt",
#     template_file="cfg1.j2",
#     priority=103,
# )
# cfg2 = ConfigTree(
#     config_file="cfg2.txt",
#     template_file="cfg2.j2",
#     priority=102,
# )
# cfg2_del = ConfigTree(
#     config_file="cfg2.j2",
#     priority=102,
# )
# print("~" * 20 + "cfg1")
# print(cfg1.config(raw=True))
# print("~" * 20 + "cfg2")
# print(cfg2.config(raw=True))

# print("~" * 20 + "compare")
# for child in cfg2.child:
#     child_in, indx = child.exists_in(cfg1, mode="templ")
#     if child_in:
#         print(child.config_line)

# print("~" * 20 + "const")
# print(cfg2.child[0].exists_in(cfg1, mode="const"))
# print("~" * 20 + "param")
# print(cfg2.child[0].exists_in(cfg1, mode="param"))
# print("~" * 20 + "templ")
# print(cfg2.child[0].exists_in(cfg1, mode="templ"))

# print(cfg2.child[0].__in(cfg1))

# print("~" * 20 + "cfg1")
# print(cfg1.config(raw=True))
# print("~" * 20 + "cfg2")
# print(cfg2.config(raw=True))
# print("~" * 20 + "test")
# cfg1.attach(cfg2)
# print(cfg1.config())

# print("~" * 20 + "merge")
# cfg1.merge(cfg2)
# print(cfg1.config())

template = ConfigTree(
    config_file="acl.j2",
)
config = ConfigTree(
    config_file="cs-chlb-dz91-oo-1.txt",
    template_file="cfg1.j2",
)

# print(config.config(raw=True))
# # test 01: config
# print("~" * 20 + "cfg1")
# print(cfg1.config(raw=True))
# print("~" * 20 + "cfg2")
# print(cfg2.config(raw=False))

# # test 02: merge
# print("~" * 20 + "cfg1 before merge")
# print(cfg1.config(raw=True))
# cfg1.merge(cfg2)
# print("~" * 20 + "cfg1 after merge")
# print(cfg1.config(raw=False))
# print("~" * 20 + "cfg2")
# print(cfg2.config(raw=False))

# # test 03: replace
# print("~" * 20 + "cfg1 before replace")
# print(cfg1.config(raw=False))
# cfg1.replace(cfg2)
# print("~" * 20 + "cfg1 after replace")
# print(cfg1.config(raw=False))
# print("~" * 20 + "cfg2")
# print(cfg2.config(raw=False))

# # test 04: copy
# cp = cfg1.child[0].copy()
# print(cp.config())

# # test 05: filter
# print("~" * 20 + "filter")
# f = cfg1.filter("address").filter("interface \S+0")
# print(f.config())

# # test 06: delete
# print("~" * 20 + "cfg1 before delete")
# print(cfg1.config(raw=False))
# print("~" * 20 + "cfg to delete")
# # f = cfg1.filter("remote-as")
# print(cfg2_del.config(raw=False))
# cfg1.delete(cfg2_del)
# print("~" * 20 + "cfg1 after delete")
# print(cfg1.config(raw=False))

# f = cfg1.filter("^interface Vlan10")
# f = cfg1.child[0].copy()
# print(f.config())
# print("~" * 20 + "cfg1")
# cfg1.delete(f)
# print(cfg1.config(raw=True))

# # test 07: intersection
# print("~" * 20 + "intersection")
# f = config.intersection(template)
# print(f.config(raw=False))

# test 08: difference
print("~" * 20 + "diff template from config (need to add to config)")
f = template.difference(config)
print(f.config(raw=False))
print("~" * 20 + "diff config from template (need to delete from config)")
f = config.difference(template)
print(f.config(raw=False))
