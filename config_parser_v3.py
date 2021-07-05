import re


class ConfigTree:
    def __init__(
        self,
        config_line="",
        config_file=None,
        config_text=None,
        template_file=None,
        parent=None,
        priority=100,
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

    def __str__(self) -> str:
        return self.format_config_line(mode="full")

    def __repr__(self) -> str:
        line = self.format_config_line(mode="full")
        return f"({id(self)}) {line}"

    def format_config_line(self, mode="") -> str:
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

    def parse_attr(self, template) -> None:
        re_attr = {}
        for attr in self.attr.keys():
            re_attr.setdefault(attr, r"\S+")
        for attr in re_attr:
            re_attr_copy = re_attr.copy()
            re_attr_copy[attr] = r"(\S+)"
            self.attr[attr] = re.findall(rf"^{template.format(**re_attr_copy)}", self.config_line)[0]

    def assigne_template(self, template):
        for template_child in template.child:
            for self_child in self.child:
                if self_child == template_child:
                    self_child.attr = template_child.attr.copy()
                    self_child.parse_attr(template_child.format_config_line(mode="re"))
                    self_child.config_line = template_child.config_line
                    self_child.assigne_template(template_child)

    def get_attr(self, config_line) -> dict:
        attr_dict = {}
        attr_list = re.findall(r"{{ \S+ }}", config_line)
        for attr in attr_list:
            attr_dict.setdefault(attr[2:-2].strip(), attr)
        return attr_dict

    def build_tree(self, config_lines):
        sections = re.split(r"\n(?=\S)", config_lines)
        for section in sections:
            self.build_sub_tree(section, self)

    def build_sub_tree(self, section, parent) -> None:
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

    def __compare__(self, self_attr: dict, obj: object, obj_attr: dict) -> bool:
        re_str_self = self.format_config_line(mode="re")
        re_str_obj = obj.format_config_line(mode="re")

        match_result_self = re.match(rf"^{re_str_self.format(**self_attr)}$", str(obj).strip())
        match_result_obj = re.match(rf"^{re_str_obj.format(**obj_attr)}$", str(self).strip())

        if match_result_self or match_result_obj:
            return True
        else:
            return False

    def eq(self, obj: object) -> bool:
        re_attr_self = self.attr.copy()
        re_attr_obj = obj.attr.copy()

        for attr_name, attr_value in re_attr_self.items():
            if re.search(r"{{ \S+ }}", attr_value):
                re_attr_self[attr_name] = r"\S+"
        for attr_name, attr_value in re_attr_obj.items():
            if re.search(r"{{ \S+ }}", attr_value):
                re_attr_obj[attr_name] = r"\S+"

        return self.__compare__(re_attr_self, obj, re_attr_obj)

    def __eq__(self, obj: object) -> bool:
        re_attr_self = {}
        re_attr_obj = {}

        for attr in self.attr.keys():
            re_attr_self.setdefault(attr, r"\S+")
        for attr in obj.attr.keys():
            re_attr_obj.setdefault(attr, r"\S+")

        return self.__compare__(re_attr_self, obj, re_attr_obj)

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

    def copy(self, with_child=True, parent=None):
        new_obj = self._copy(with_child=with_child, parent=parent)
        root = new_obj
        while root.parent is not None:
            root = root.parenst
        return root
        # pass

    def _copy(self, with_child, parent):
        if self.parent is not None and parent is None:
            # parent = self.parent
            parent = self.parent._copy(with_child=False, parent=None)
        new_obj = ConfigTree(
            config_line=self.config_line,
            parent=parent,
            priority=self.priority,
        )
        new_obj.attr = self.attr.copy()
        if not with_child:
            return new_obj
        for child in self.child:
            _ = child._copy(with_child=with_child, parent=new_obj)
        return new_obj

    def full_path(self):
        if self.parent is not None:
            parent = ConfigTree(priority=self.priority)
            parent.attr = self.parent.attr.copy()
            parent.config_line = self.parent.config_line
            parent.child.append(self)
            parent.parent = self.parent.parent
            self.parent = parent
            return parent.full_path()
        else:
            return self

    def merge(self, obj):
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

    def replace(self, obj):
        for obj_child in obj.child:
            for indx, self_child in enumerate(self.child):
                if obj_child.eq(self_child):
                    self_child.parent = None
                    obj_child.parent = self
                    self.child.pop(indx)
                    self.child.insert(indx, obj_child)

    def __filter(self, string, no_child):
        result = []
        for child in self.child:
            r = re.search(rf"{string.strip()}", str(child).strip())
            if r:
                result.append(child.copy())
                # result.append(child)
                # new_child = child.full_path()
                # if no_child:
                #     new_child.child = []
                # return result
                # result.append(new_child)
            if len(child.child) != 0 and not (r and no_child):
                # if len(child.child) != 0:
                result.extend(child.__filter(string, no_child))
        return result

    def filter(self, string, no_child=False):
        root = ConfigTree(priority=self.priority)
        filter_result = []
        filter_result.extend(self.__filter(string, no_child=no_child))
        for child in filter_result:
            root.merge(child)

            # child_copy = child.copy()
            # child_full = child.full_path()
            # root.merge(child_full)
        # if no_child:
        #     root.delete_child(string)
        return root

    def delete(self, obj):
        for obj_child in obj.child:
            for self_child in self.child:
                if self_child.eq(obj_child):
                    if len(obj_child.child) != 0:
                        self_child.delete(obj_child)
                    else:
                        print(self_child)


cfg1 = ConfigTree(
    config_file="cfg1.txt",
    template_file="cfg.j2",
    priority=101,
)
# cfg2 = ConfigTree(
#     config_file="cfg2.txt",
#     # template_file="cfg.j2",
#     priority=102,
# )
# cfg1.merge(cfg2)
# cfg1.replace(cfg2)
# print("~" * 20)
# print(cfg1.get_config())
# print("~" * 20)
# to_del = cfg1.filter("router bgp", no_child=True)

# print(to_del.get_config())
# print("~" * 20)
# print(cfg1.get_config())
# print("~" * 20)
# print(cfg1.get_config())


print("~" * 20)
# f1 = cfg1.child[5].child[1].copy()
# print(f1.get_config())
# print("~" * 20)
# print(cfg1.get_config())
# print("~" * 20)
f1 = cfg1.filter("address")
print(f1.get_config())
print("~" * 20)
print(cfg1.get_config())
