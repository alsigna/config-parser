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
        """
        Text config to tree converter.

        Args:
            config_line (str, optional): single line. Defaults to "".
            config_file (str, optional): file to read config from. Defaults to None.
            config_text (str, optional): config in text format. Defaults to None.
            template_file (str, optional): file to read template from. Defaults to None.
            parent (ConfigTree, optional): parent node. Defaults to None.
            priority (int, optional): priority for merging. Defaults to 100.
        """
        # link to parent object
        self.parent = parent
        # list of child objects
        self.child = []
        #  raw config line
        self.config_line = config_line
        # dict with parsed attributes, if exists - '{{ NAME }}'
        self.attr = self._get_attr(config_line)
        # set priority for meerging
        self.priority = priority
        # mark + or - for comparing result, like to git notation
        self.action = ""
        # skip line (full matching)
        self.skip_line = [
            "!",
            "end",
            "exit-address-family",
        ]
        # skip line which begins with
        self.skip_line_begins_with = [
            "Building configuration",
            "Current configuration",
        ]
        # if parent specified, add us to parent's childs
        if parent is not None:
            parent.child.append(self)
        # if config from file - read config to mem
        if config_file is not None:
            with open(config_file, "r") as file_:
                config_text = file_.read().strip()
        # if config was readed from file or direct specifid - build tree
        if config_text is not None:
            config_text = self._preprocess_config(config_text)
            self._build_tree(config_text)
        # parce and assigne template to config
        if template_file is not None:
            with open(template_file, "r") as file_:
                template_text = file_.read().strip()
            self._assigne_template(ConfigTree(config_text=template_text))

    def __str__(self: ConfigTree) -> str:
        # config line with values instead of parameters
        return self._format_config_line(mode="full")

    def __repr__(self: ConfigTree) -> str:
        # config line with values instead of parameters and ID
        line = self._format_config_line(mode="full")
        return f"({id(self)}) {line}"

    def _remove_banners(self: ConfigTree, config_text: str) -> str:
        # TODO: add banner parsing
        """
        remove banners from config.

        Args:
            config_text (str): initial config
        Returns:
            str: cleared config
        """
        while True:
            banner = re.search(r"\nbanner\s+\S+\s+(\^\S)", config_text)
            if not banner:
                return config_text
            config_text = re.sub(
                rf"banner \S+ \{banner.group(1)}[\S\s]*?\{banner.group(1)}",
                "",
                config_text,
            )

    def _remove_cert_chain(self: ConfigTree, config_text: str) -> str:
        """
        Remove sections with PIK cert.

        Args:
            config_text (str): initial config

        Returns:
            str: cleared config
        """
        config_text = re.sub(
            r"crypto\s+pki\s+certificate\s+chain\s+[\s\S]*?\n(?=\S)",
            "",
            config_text,
        )
        return config_text

    def _remove_junk_lines(self: ConfigTree, config_text: str) -> str:
        """
        Remove junk lines which describes skip_line_begins_with list.

        Args:
            config_text (str): initial config

        Returns:
            str: cleared config
        """
        for line in self.skip_line_begins_with:
            config_text = re.sub(rf"{line}.*\n", "", config_text)
        return config_text

    def _remove_empty_lines(self: ConfigTree, config_text: str) -> str:
        """
        Remove empty lines: several consecutive \\n.

        Args:
            config_text (str): initial config

        Returns:
            str: cleared config
        """
        config_text = re.sub(
            r"\n\n+(?=\S)",
            "\n",
            config_text,
        )
        return config_text

    def _search(self: ConfigTree, string: str, with_child: bool, raw: bool) -> list:
        """
        Internal function for recursive search.

        Args:
            string (str): String to search. Can be regex
            with_child (bool): Deep search, in child objects also. Defaults to True.
            raw (bool): Search in templated config (True) or compiled config (False). Defaults to False.

        Returns:
            list: list of finded objects.
        """
        result = []
        for child in self.child:
            if raw:
                line = str(child.config_line).strip()
            else:
                line = str(child).strip()
            match = re.search(rf"{string.strip()}", line)
            if match:
                result.append(child.copy(with_child=with_child))
            if len(child.child) != 0 and (not match or with_child):
                result.extend(child._search(string, with_child, raw))
        return result

    def _format_config_line(self: ConfigTree, mode: str = "re") -> str:
        """
        Format string for printing or compiling.

        Args:
            mode (str, optional):
                re: line for using with re: "access-list {ACL} in"
                full: line with values instead of attr_name: "access-list 10 in"

        Returns:
            str: formatted line
        """
        if (
            "{" not in self.config_line
            and "}" not in self.config_line
            and "[" not in self.config_line
            and "]" not in self.config_line
        ):
            # if no special symbols
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
            # format string with values
            cmd = cmd.format(**self.attr)
            cmd = re.sub(ccb, "}", cmd)
            cmd = re.sub(ocb, "{", cmd)
            cmd = re.sub(csb, "]", cmd)
            cmd = re.sub(osb, "[", cmd)
            return cmd
        else:
            return cmd

    def _preprocess_config(self: ConfigTree, config_text: str) -> str:
        """
        Preprocessing config: clear banner, junk/empty lines etc.

        Args:
            config_text (str): initial config

        Returns:
            str: cleared config
        """
        config_text = self._remove_banners(config_text)
        config_text = self._remove_cert_chain(config_text)
        config_text = self._remove_junk_lines(config_text)
        config_text = self._remove_empty_lines(config_text)
        return config_text

    def _build_sub_tree(self: ConfigTree, section: str, parent: ConfigTree) -> None:
        """
        Parse cnofig line and build sub-tree if this is susction.

        Args:
            section (str): config text
            parent (ConfigTree): parent object
        """
        lines = section.split("\n")
        # if no line or line should be skiped, or this is comment which is started from
        # "skip_line", like "!some comment need to be skipped"
        if len(lines) == 0:
            return
        elif len(lines[0]) == 0:
            return
        elif lines[0].strip() in self.skip_line or lines[0][0] in self.skip_line:
            return
        # store config line
        child = ConfigTree(config_line=lines[0].strip(), parent=parent, priority=self.priority)
        if len(lines) == 1:
            return
        # shift subsection to the left (remove spaces from the line begin)
        spaces = re.match(r"^(\s+)", lines[1]).group(1)
        sub_lines = [line.replace(spaces, "", 1) for line in lines[1:]]
        sub_section = "\n".join(sub_lines)
        # recursively build tree from section
        child._build_tree(sub_section)

    def _build_tree(self: ConfigTree, config_text: str) -> None:
        """
        Buld tree from config.

        Args:
            config_text (str): config in plain text
        """
        sections = re.split(r"\n(?=\S)", config_text)
        for section in sections:
            self._build_sub_tree(section, self)

    def _assigne_template(self: ConfigTree, obj: ConfigTree) -> None:
        """
        Assigne template to config.
        For every self leaf (raw config) is checking if line is exist in assigned template.\n
        If exists:\n
         - copping attr dict from template\n
         - replace attr name in dict.values with real values\n
         - replace original string with template string\n
        original string (self):\n
        "ip address 192.168.1.1 255.255.255.0", attr = {}\n
        template:\n
        "ip address {IP_ADDR} {MASK}", attr dict: {"IP_ADDR": "IP_ADDR", "MASK": "MASK"}\n
        result (replaced original leaf):\n
        "ip address {IP_ADDR} {MASK}", attr dict: {"IP_ADDR": "192.168.1.1", "MASK": "255.255.255.0"}\n

        Args:
            obj (ConfigTree): Object with template (need to be tree).
        """
        for self_child in self.child:
            indx, match = self_child._exists_in(obj, bidir=True)
            if match:
                self_child.attr = obj.child[indx].attr.copy()
                self_child._parse_attr(obj.child[indx]._format_config_line(mode="re"))
                self_child.config_line = obj.child[indx].config_line
                self_child._assigne_template(obj.child[indx])
                obj.child.pop(indx)

    def _parse_attr(self: ConfigTree, template: str) -> None:
        """
        Parse attribute value of original config based on template.
        Ex:
        original string (self):
            "ip address 192.168.1.1 255.255.255.0" (attr dict: {"IP_ADDR": "IP_ADDR", "MASK": "MASK"})
        template string:
            "ip address {IP_ADDR} {MASK}" (attr dict: {"IP_ADDR": "IP_ADDR", "MASK": "MASK"})
        result:
            ovrride original attr dict to {"IP_ADDR": "192.168.1.1", "MASK": "255.255.255.0"}

        Args:
            template (str): template sting in "re format" (check _format_config_line)
        """
        re_attr = {}
        for attr in self.attr.keys():
            re_attr.setdefault(attr, r"\S+")
        for attr in re_attr:
            re_attr_copy = re_attr.copy()
            re_attr_copy[attr] = r"(\S+)"
            self.attr[attr] = re.findall(rf"^{template.format(**re_attr_copy)}", self.config_line)[0]

    def _get_attr(self: ConfigTree, config_line: str) -> dict:
        """
        Extract attribute from template line.

        Args:
            config_line (str): config line, ex: "ntp server {{ NTP }}"

        Returns:
            dict: dict with name and value, ex: {"NTP": "NTP"}.
        """
        attr_dict = {}
        attr_list = re.findall(r"{{ \S+ }}", config_line)
        for attr in attr_list:
            attr_dict.setdefault(attr[2:-2].strip(), attr)
        return attr_dict

    def _exists_in(
        self: ConfigTree,
        obj: ConfigTree,
        param: bool = True,
        templ: bool = True,
        bidir: bool = False,
    ) -> tuple:
        """
        Check if obj exists in self (for every leaf of object).

        Args:
            self (ConfigTree): object where is tried to find matching.
            obj (ConfigTree): object for which is tried to find match in self.
            param (bool, optional): _description_. Defaults to True.
            templ (bool, optional): _description_. Defaults to True.
            bidir (bool, optional): _description_. Defaults to False.

        Returns:
            tuple: (index,True) in case of success, (None,False) in case of no match.
            index - index in child list.
        """
        for indx, obj_child in enumerate(obj.child):
            result = obj_child.eq(self, param=param, templ=templ, bidir=bidir)
            if result:
                return indx, True
        return None, False

    def _match_to_template(self: ConfigTree, obj: ConfigTree, param: bool) -> bool:
        """Match config_line obj to self with regex features.

        Args:
            self (ConfigTree): object to match to
            obj (ConfigTree): object to match from
            param (bool, optional): consider or not parsed parameters. Defaults to False.
            Important. If param=True, parsed values are ignored.
            example: line = access-list {{ ACL }} | {"ACL": 10}
            - param=True: line is considered as "access-list \\S+"
            - param=False: line is considered as "access-list 10"

        Returns:
            bool: equal or not
        """

        attr = obj.attr.copy()
        config_line = obj._format_config_line(mode="re")
        for attr_name, attr_value in attr.items():
            if not param or re.search(r"{{ \S+ }}", attr_value):
                attr[attr_name] = r"\S+"
        match = re.match(rf"^{config_line.format(**attr)}$", str(self).strip())
        if match:
            return True
        else:
            return False

    def _copy_obj_attributes(self: ConfigTree, obj: ConfigTree) -> None:
        self.config_line = obj.config_line
        self.parent = obj.parent
        self.priority = obj.priority
        self.action = obj.action
        self.attr = obj.attr.copy()

    def _copy(
        self: ConfigTree,
        with_child: bool,
        parent: ConfigTree,
    ) -> ConfigTree:
        """Recursively copying objects.

        Args:
            with_child (bool): copy child or not
            parent (ConfigTree): parent object

        Returns:
            ConfigTree: copy of original object
        """

        # bottom leaf can not be copied without his parent
        # restoring tree from copied leaf up to root
        if self.parent is not None and parent is None:
            parent = self.parent._copy(with_child=False, parent=None)
        # new_obj = ConfigTree(
        #     config_line=self.config_line,
        #     parent=parent,
        #     priority=self.priority,
        # )
        # new_obj.attr = self.attr.copy()
        new_obj = ConfigTree(parent=parent)
        new_obj._copy_obj_attributes(self)
        new_obj.parent = parent
        if not with_child:
            return new_obj
        for child in self.child:
            _ = child._copy(with_child=with_child, parent=new_obj)
        return new_obj

    def show_config(
        self: ConfigTree,
        symbol: str = " ",
        raw: bool = False,
        _symbol_count: int = -1,
    ) -> str:
        """
        Display config in text format.

        Args:
            symbol (str, optional): padding symbol for sub-section. Defaults to " ".
            raw (bool, optional): display with args (True) or values (False). Defaults to False.
            symbol_count (int, optional): padding symbol count. Defaults to -1.
            Because first level is root objects with no config lines at all.

        Returns:
            str: text config
        """
        if self.parent is None:
            config_list = []
        else:
            if raw:
                params = " |> " + str(self.attr) if len(self.attr) else ""
                config_list = [self.action + symbol * _symbol_count + self.config_line + params]
            else:
                config_list = [self.action + symbol * _symbol_count + str(self)]
        for child in self.child:
            config_list.append(child.show_config(symbol=symbol, raw=raw, _symbol_count=_symbol_count + 1))
        return "\n".join(config_list)

    def search(
        self: ConfigTree,
        string: str,
        with_child: bool = True,
        raw: bool = False,
    ) -> ConfigTree:
        """
        Search text in config.

        Args:
            string (str): String to search. Can be regex
            with_child (bool, optional): Deep search, in child objects also. Defaults to True.
            raw (bool, optional): Search in templated config (True) or compiled config (False). Defaults to False.

        Returns:
            ConfigTree: Tree object, can be used as original.
        """
        root = ConfigTree(priority=self.priority)
        filter_result = []
        filter_result.extend(self._search(string, with_child, raw))
        for child in filter_result:
            root.merge(child)
        return root

    def eq(
        self: ConfigTree,
        obj: ConfigTree,
        param: bool = False,
        templ: bool = True,
        bidir: bool = False,
        section: bool = False,
    ) -> bool:
        """Compare two objects with each other.

        Args:
            obj (ConfigTree): object to compare with.

            param (bool, optional): consider or not parsed parameters. Defaults to False.
            + obj1: config_line = "ntp server {{ NTP }}", attr = {"NTP": "1.2.3.4"}
            + obj2: config_line = "ntp server {{ NTP }}", attr = {"NTP": "4.3.2.1"}
            + if param=False, result is True (only config_line are comparing)
            + if param=True, result is False (each config_line is compiled with attr
            and after that comparing with other)

            templ (bool, optional): _description_. Defaults to True.

            bidir (bool, optional): compare in two way. like to obj1.eq(obj2) OR obj2.eq(obj1). Defaults to False.

            section (bool, optional): drill down to childs or not. Defaults to False.
            config1:
            router bgp 65000
              bgp router-id 1.2.3.4
            config2:
            router bgp 65000
              bgp router-id 4.3.2.1
            if during comparing bgp leaf section = False, result will be True, if section = True, result will be False

        Returns:
            bool: _description_
        """

        # recursevely drill down if full section need to be compared
        if section:
            if len(self.child) != len(obj.child):
                return False
            for obj_child in obj.child:
                indx, match = obj_child._exists_in(self, param, templ, bidir)
                if not match:
                    return False
                else:
                    if not obj_child.eq(self.child[indx], param, templ, bidir, section):
                        return False
            return obj.eq(self, param, templ, bidir)

        # comparing full compiled lines (value instead of parameters), see __str__
        # if both lines with parameters - checking raw config_lines also to check that
        # parameter's name also are matched between objects.
        if str(self) == str(obj):
            if len(self.attr) != 0 and len(obj.attr) != 0:
                if self.config_line == obj.config_line:
                    return True
                else:
                    return False
            else:
                return True
        # if we are here, that compiled lines does not match
        # return False if strict math is requared (no templates)
        # TODO: check if templ can be replaced with param
        if not templ:
            return False

        # template (re) comparing area.
        if bidir:
            match_result_obj = self._match_to_template(obj, param)
        #     attr_obj = obj.attr.copy()
        #     str_obj = obj._format_config_line(mode="re")
        #     for attr_name, attr_value in attr_obj.items():
        #         if not param or re.search(r"{{ \S+ }}", attr_value):
        #             attr_obj[attr_name] = r"\S+"
        #     match_result_obj = re.match(rf"^{str_obj.format(**attr_obj)}$", str(self).strip())
        else:
            match_result_obj = False

        # attr_self = self.attr.copy()
        # str_self = self._format_config_line(mode="re")
        # for attr_name, attr_value in attr_self.items():
        #     if not param or re.search(r"{{ \S+ }}", attr_value):
        #         attr_self[attr_name] = r"\S+"
        # match_result_self = re.match(rf"^{str_self.format(**attr_self)}$", str(obj).strip())
        match_result_self = obj._match_to_template(self, param)

        if match_result_self or match_result_obj:
            if len(self.attr) != 0 and len(obj.attr) != 0:
                if self.config_line == obj.config_line:
                    return True
                else:
                    return False
            else:
                return True

        return False

    def copy(
        self: ConfigTree,
        with_child: bool = True,
        parent: ConfigTree = None,
    ) -> ConfigTree:
        """Copy object.

        Args:
            with_child (bool, optional): drill down to childs. Defaults to True.
            parent (ConfigTree, optional): can be copied to other parend. Defaults to None.

        Returns:
            ConfigTree: copy of object
        """
        root = self._copy(with_child=with_child, parent=parent)
        # finding root (top) leaf
        while root.parent is not None:
            root = root.parent
        return root

    def merge(
        self: ConfigTree,
        obj: ConfigTree,
        param: bool = False,
        templ: bool = True,
        bidir: bool = False,
    ) -> None:
        """Merge two ConfigTree objects.

        Args:
            obj (ConfigTree): object to merge from.
            param (bool, optional): consider or not parsed parameters. Defaults to False.
            templ (bool, optional): _description_. Defaults to True.
            bidir (bool, optional): compare in two way. like to obj1.eq(obj2) OR obj2.eq(obj1). Defaults to False.
        """

        if (
            self.eq(obj, param, templ, bidir)  # self and obj are mathed with each other
            and len(self.child) == 0  # both elements are bottom leafs
            and len(obj.child) == 0
            and self.priority < obj.priority  # obj priority is higher than self
        ):
            if not obj.attr:
                obj.attr = self.attr.copy()
                obj._parse_attr(self._format_config_line(mode="re"))
                obj.config_line = self.config_line

            self._copy_obj_attributes(obj)
            # self.config_line = obj.config_line
            # self.attr = obj.attr.copy()
            # self.priority = obj.priority
            # self.action = obj.action

        for obj_child in obj.child:
            indx, match = obj_child._exists_in(self, param, templ, bidir)
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
        """

        Args:
            self (ConfigTree): _description_
            obj (ConfigTree): _description_
            param (bool, optional): _description_. Defaults to True.
            templ (bool, optional): _description_. Defaults to True.
            bidir (bool, optional): _description_. Defaults to False.
        """
        for obj_child in obj.child:
            indx, match = obj_child._exists_in(self, param, templ, bidir)
            if match:
                self.child[indx].parent = None
                self.child.pop(indx)
                new_obj = obj_child._copy(with_child=True, parent=None)
                new_obj.parent = self
                self.child.insert(indx, new_obj)

    def delete(
        self: ConfigTree,
        obj: ConfigTree,
        param: bool = True,
        templ: bool = True,
        bidir: bool = False,
    ) -> None:
        for obj_child in obj.child:
            indx, match = obj_child._exists_in(self, param, templ, bidir)
            if match:
                if len(obj_child.child) != 0:
                    self.child[indx].delete(obj_child)
                if len(self.child[indx].child) == 0 or (
                    len(obj_child.child) == 0 and len(self.child[indx].child) != 0
                ):
                    self.child.pop(indx)
                    obj_child.parent = None

    def __intersection(self: ConfigTree, obj: ConfigTree) -> list:
        result = []
        for obj_child in obj.child:
            indx, match = obj_child._exists_in(self, bidir=True)
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
            indx, match = self_child._exists_in(remove_obj)
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
#     template_file="cfg1.j2",
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


# cfg3 = ConfigTree(
#     # config_file="cfg1.txt",
#     config_file="full_config.txt",
#     # template_file="cfg1.j2",
# )
# tmpl = ConfigTree(
#     # config_file="cfg2.j2",
#     config_file="full_config.j2",
#     # template_file="cfg2.j2",
# )
# # print(cfg3.config())
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
# tmpl.merge(dual_hub)

# intersection, add, rem, full = cfg3.compliance(tmpl)
# print("~" * 20 + "tmpl.intersection(cfg3)")
# print(intersection.config(raw=True))
# print("~" * 20 + "diff template from config (need to add to config)")
# print(add.config(raw=True))
# print("~" * 20 + "diff config from template (need to delete from config)")
# print(rem.config(raw=True))
# print("~" * 20 + "full config")
# print(full.config(raw=True))


if __name__ == "__main__":
    cfg1 = ConfigTree(
        config_file="./data/cfg1_sample.txt",
        template_file="./data/template_sample.j2",
        priority=110,
    )
    cfg2 = ConfigTree(
        config_file="./data/cfg2_sample.txt",
        template_file="./data/template_sample.j2",
        priority=120,
    )
    template = ConfigTree(
        config_file="./data/template_sample.j2",
        priority=130,
    )
    cfg1.replace(cfg2)
    print(cfg1.show_config())
