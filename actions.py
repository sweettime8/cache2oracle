from enum import member

from flask import Blueprint, request, render_template, redirect, url_for, flash, Response, jsonify
import re
import os
import xml.dom.minidom
import logging
import textwrap

# Cấu hình logging
logging.basicConfig(filename='logfile.txt', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

logging.info('#################################################')
logging.info('#                 Start APP                     #')
logging.info('#################################################')

actions = Blueprint('actions', __name__, template_folder='templates')


# @actions.route('/')
# def index():
#     return render_template('index.html')


@actions.route('/convert-cls', methods=['POST', 'GET'])
def convert_cls():
    return render_template('convert-cls.html')


@actions.route('/convert-mac', methods=['POST', 'GET'])
def convert_mac():
    return render_template('convert-mac.html')


@actions.route('/', methods=['POST', 'GET'])
def convert_code():
    return render_template('convert-code.html')


oracle_keywords = [
    'ACCESS', 'ADD', 'ALL', 'ALTER', 'AND', 'ANY', 'AS', 'ASC', 'AUDIT', 'BETWEEN',
    'BY', 'CHAR', 'CHECK', 'CLUSTER', 'COLUMN', 'COMMENT', 'COMPRESS', 'CONNECT',
    'CREATE', 'CURRENT', 'DATE', 'DECIMAL', 'DEFAULT', 'DELETE', 'DESC', 'DISTINCT',
    'DROP', 'ELSE', 'EXCLUSIVE', 'EXISTS', 'FILE', 'FLOAT', 'FOR', 'FROM', 'GRANT',
    'GROUP', 'HAVING', 'IDENTIFIED', 'IMMEDIATE', 'IN', 'INCREMENT', 'INDEX', 'INITIAL',
    'INSERT', 'INTEGER', 'INTERSECT', 'INTO', 'IS', 'LEVEL', 'LIKE', 'LOCK', 'LONG',
    'MAXEXTENTS', 'MINUS', 'MLSLABEL', 'MODE', 'MODIFY', 'NOAUDIT', 'NOCOMPRESS',
    'NOT', 'NOWAIT', 'NULL', 'NUMBER', 'OF', 'OFFLINE', 'ON', 'ONLINE', 'OPTION',
    'OR', 'ORDER', 'PCTFREE', 'PRIOR', 'PRIVILEGES', 'PUBLIC', 'RAW', 'RENAME',
    'RESOURCE', 'REVOKE', 'ROW', 'ROWID', 'ROWNUM', 'ROWS', 'SELECT', 'SESSION',
    'SET', 'SHARE', 'SIZE', 'SMALLINT', 'START', 'SUCCESSFUL', 'SYNONYM', 'SYSDATE',
    'TABLE', 'THEN', 'TO', 'TRIGGER', 'UID', 'UNION', 'UNIQUE', 'UPDATE', 'USER',
    'VALIDATE', 'VALUES', 'VARCHAR', 'VARCHAR2', 'VIEW', 'WHENEVER', 'WHERE', 'WITH'
]


@actions.route('/start-convert-cls', methods=['POST', 'GET'])
def start_convert_cls():
    try:
        if request.method == 'POST':
            logging.info("#### [start-convert-cls] ####")
            files = request.files.getlist('filepond')

            for xml_file in files:
                data = xml_file.getvalue()
                content = xml.dom.minidom.parseString(data)
                # print(content.toprettyxml(newl=''))

                class_node = content.getElementsByTagName("Class")[0]
                class_name = class_node.getAttribute("name")

                # Loại bỏ dấu "."
                input_str = class_name.replace(".", "")
                # Thêm dấu "_" trước chữ in hoa
                output_str = ''.join(['_' + c if c.isupper() else c for c in input_str]).lstrip('_')
                # Thêm "_CLS" vào cuối
                output_str += "_CLS"
                file_convert_name = output_str.upper()
                file_convert = "CLS_RESULT/" + file_convert_name + ".sql"

                isExist = os.path.exists("CLS_RESULT")
                if not isExist:
                    os.makedirs("CLS_RESULT")

                package_header = f"CREATE OR REPLACE PACKAGE {file_convert_name} AS "
                package_content = f"""
                
    /*****************************************************
     *  PACKAGE NAME: Use for replacement $ZNAME in Caché
     *****************************************************/
    PACKAGE_NAME VARCHAR2(150) := '{file_convert_name}';
    /*******************************************************
     *  DECLARE METHODS: Declare function or procedure here
     *******************************************************/
                """

                package_end = f"""
    ----------------- END IMPLEMENTATION -------------------
END {file_convert_name};
/
                """

                methods = content.getElementsByTagName("Method")
                query_cls = content.getElementsByTagName("Query")

                package_body = f"""
    ----------------- END DECLARE METHODS -------------------
END {file_convert_name};
/
CREATE OR REPLACE PACKAGE BODY {file_convert_name} AS """
                package_body += f"""
                
    /*******************************************************
     *  IMPLEMENTATION: Implement logic here
     *******************************************************/            
                            """

                for i in range(len(methods)):
                    method_name = methods[i].getAttribute("name")
                    # Không migrate Execute,Fetch,Close
                    if ("Execute" in method_name) or ("Fetch" in method_name) or ("Close" in method_name):
                        continue

                    # Tìm phần tử <Description> trong phần tử <Method> hiện tại
                    description_method = methods[i].getElementsByTagName("Description").item(0)
                    if description_method:
                        # Lấy nội dung của FormalSpec
                        description_method_value = description_method.firstChild.nodeValue
                        # chuyen doi line cho java doc
                        lines = description_method_value.split('\n')
                        formatted_description = "/**\n"
                        for line in lines:
                            if line.strip() != "":
                                formatted_description += f"     * {line}\n"
                        formatted_description += "    **/"
                        formatted_description = formatted_description.replace("<BR>", "")
                    else:
                        description_method_value = ""
                        formatted_description = ""

                    # Tìm phần tử <FormalSpec> trong phần tử <Method> hiện tại
                    formal_spec = methods[i].getElementsByTagName("FormalSpec").item(0)

                    if formal_spec:
                        # Lấy nội dung của FormalSpec
                        formal_spec_value = convert_formal_spec(formal_spec.firstChild.nodeValue)
                    else:
                        formal_spec_value = ""

                    # Tìm phần tử <ReturnType> trong phần tử <Method> hiện tại
                    return_type = methods[i].getElementsByTagName("ReturnType").item(0)
                    if return_type:
                        return_type_value = convert_data_type_file(return_type.firstChild.nodeValue)
                    else:
                        return_type_value = ""

                    # mrd check lại formal_spec_value ( đối với OUT Có default thì khai báo trong begin, OUT không được có default value)
                    array_formal_spec_value = formal_spec_value.split(",")
                    array_new = []
                    if array_formal_spec_value:
                        array_default_value_method = []
                        for item_new_value in array_formal_spec_value:
                            if ("OUT" in item_new_value) and ("DEFAULT" in item_new_value):
                                # sửa lại format in ra
                                item_out_value = item_new_value.split("DEFAULT")[0]
                                # lưu trữ lại param và default value
                                spec_param_name = item_new_value.split("OUT")[0]
                                default_value = item_new_value.split("DEFAULT")[1]
                                if default_value == "''":
                                    default_value = "NULL"
                                array_default_value_method.append((spec_param_name, default_value))

                            else:
                                item_out_value = item_new_value

                            array_new.append(item_out_value)

                        # Kết hợp các phần tử lại với nhau và ngăn cách bằng dấu phẩy
                        output_str_formal_spec_value = ','.join(array_new)
                        formal_spec_value = output_str_formal_spec_value

                    # Đọc <Implementation> trong phần tử <Method> hiện tại
                    imp_value = methods[i].getElementsByTagName("Implementation").item(0)
                    if imp_value:
                        imp_value = imp_value.firstChild.nodeValue
                        pattern = r'#Include\s+(\S+)'
                        # Sử dụng re.findall để tìm tất cả các #Include trong đoạn văn bản
                        includes = re.findall(pattern, imp_value)
                        include_list = ""
                        if includes:
                            include_list += f"""
        -- Declare include list to know where constants should be                    
        INCLUDE_LIST STRING_ARRAY := STRING_ARRAY("""
                            pattern_storage = '\.(s|S)torage'
                            for include in includes:
                                if not re.search(pattern_storage, include):
                                    include_list += f"""'{include}',"""
                            # Loại bỏ dấu "," cuối cùng và thêm dấu ");"
                            if include_list.endswith(","):
                                include_list = include_list[:-1] + ');'
                            else:
                                include_list += ");"

                        pattern_constant = r'#Define\s+(\w+)\s+"?([^"\n]+)"?\s*'
                        # Sử dụng re.findall để tìm tất cả các #Define trong đoạn văn bản
                        find_defines = re.findall(pattern_constant, imp_value, flags=re.IGNORECASE)
                        output_constants = ""
                        if find_defines:
                            for name, value in find_defines:
                                output_constants += f"""
        {name} VARCHAR2(150) := '{value}';
                                """

                    else:
                        imp_value = ""

                    # Sử dụng biểu thức chính quy để kiểm tra xem "Quit" có tồn tại trong mã Implementation hay không
                    match_quit = re.findall(r'(Q|q)uit\s+([^\n]+)\n', imp_value)
                    if match_quit:
                        # Kiểm tra xem "Quit" có đi kèm với khoảng trắng và sau đó là ky tu bang chu cai
                        last_match = match_quit[-1]
                        quit_command = last_match[0]  # "Q" hoặc "q"
                        letter_after_quit = last_match[1]  # Ký tự chữ sau "Quit" (nếu có)
                        check_match = re.search(r'([^\n]+)', letter_after_quit.strip())

                        if check_match and return_type_value != "":
                            # là function
                            package_content += f"""
    {formatted_description}"""
                            if formal_spec_value == "":
                                package_content += f"""
    FUNCTION {method_name} RETURN {return_type_value};   
                                                """
                                package_body += f"""
    FUNCTION {method_name} RETURN {return_type_value} IS"""
                            else:
                                package_content += f"""
    FUNCTION {method_name}({formal_spec_value}) RETURN {return_type_value};    
                            """
                                package_body += f"""
    FUNCTION {method_name}({formal_spec_value}) RETURN {return_type_value} IS"""
                            if include_list != "":
                                package_body += f"""
        {include_list}
                            """
                            if output_constants:
                                package_body += f"""
        {output_constants}
                            """

                            output_default_value_method = ""
                            for item_set_value_method in array_default_value_method:
                                item_name = item_set_value_method[0]
                                item_value = item_set_value_method[1]
                                output_default_value_method += item_name + ":=" + item_value + ";\n"

                            package_body += f"""
    BEGIN
                            """
                            if output_default_value_method == "":
                                package_body += f"""
        -- TODO : Implement method body
        RETURN NULL;   
    END {method_name};
                            """
                            else:
                                package_body += f"""
        {output_default_value_method}
        -- TODO : Implement method body
        RETURN NULL;   
    END {method_name};          
                                """
                        else:
                            # là procedure
                            # check if formal_spec_value == "" thi bo dau ()
                            if formal_spec_value != "":
                                package_content += f"""
    {formatted_description}                        
    PROCEDURE {method_name}({formal_spec_value});        
                                                    """
                                package_body += f"""
    PROCEDURE {method_name}({formal_spec_value}) IS"""
                            else:
                                package_content += f"""
    {formatted_description}                        
    PROCEDURE {method_name};        
                                                 """
                                package_body += f"""
    PROCEDURE {method_name} IS"""

                            if include_list != "":
                                package_body += f"""
        {include_list}
                            """
                            if output_constants:
                                package_body += f"""
        {output_constants}
                            """
                            package_body += f"""
    BEGIN
        -- TODO : Implement method body
        RETURN;
    END {method_name};
                            """
                    elif return_type_value == "":
                        if formal_spec_value != "":
                            package_content += f"""
                        {formatted_description}                        
    PROCEDURE {method_name}({formal_spec_value}) ;        
                                          """
                            package_body += f"""
    PROCEDURE {method_name}({formal_spec_value}) IS"""
                        else:
                            package_content += f"""
                        {formatted_description}                        
    PROCEDURE {method_name};        
                                              """
                            package_body += f"""
    PROCEDURE {method_name} IS"""

                        if include_list != "":
                            package_body += f"""
    {include_list}
                                           """
                        if output_constants:
                            package_body += f"""
    {output_constants}
                                                """
                        package_body += f"""
    BEGIN
        -- TODO : Implement method body
        RETURN;
    END {method_name};
                                                """

                #### end for method

                #### Start for query
                for i in range(len(query_cls)):
                    query_name = query_cls[i].getAttribute("name")
                    if query_name == "GetSyukoList":
                        print("mrd")
                    # Tìm phần tử <Description> trong phần tử <Query> hiện tại
                    description_query = query_cls[i].getElementsByTagName("Description").item(0)
                    if description_query:
                        # Lấy nội dung của description
                        description_query_value = description_query.firstChild.nodeValue
                        # chuyen doi line cho java doc
                        lines = description_query_value.split('\n')
                        formatted_description_query = "/**\n"
                        for line in lines:
                            if line.strip() != "":
                                formatted_description_query += f"     * {line}\n"
                        formatted_description_query += "    **/"
                        formatted_description_query = formatted_description_query.replace("<BR>", "")
                    else:
                        formatted_description_query = ""

                    # Tìm phần tử <FormalSpec> trong phần tử <Query> hiện tại
                    formal_spec_query = query_cls[i].getElementsByTagName("FormalSpec").item(0)
                    if formal_spec_query:
                        # Lấy nội dung của FormalSpec
                        formal_spec_query_value = convert_formal_spec(formal_spec_query.firstChild.nodeValue)
                    else:
                        formal_spec_query_value = ""

                    # Tìm phần tử <Parameter> trong phần tử <Query> hiện tại
                    parameter_query = query_cls[i].getElementsByTagName("Parameter").item(0)
                    if parameter_query:
                        # Lấy nội dung của FormalSpec
                        parameter_query_query_value = convert_query_parameter(parameter_query.getAttribute("value"))
                        # Tách chuỗi thành danh sách các tham số
                        # parameter_query_query_value = parameter_query_query_value.split(", ")

                        # Tạo chuỗi mới với dấu xuống dòng sau mỗi tham số
                        # parameter_query_query_value = ",\n         ".join(parameter_query_query_value)
                    else:
                        parameter_query_query_value = ""

                    declare_record_query = f"""
    TYPE record{query_name}Tmp IS RECORD (
        {parameter_query_query_value}
    );
    TYPE table{query_name} IS TABLE OF record{query_name}Tmp;
                                    """

                    if formal_spec_query_value != "":
                        package_content += f"""
    {formatted_description_query}
    {declare_record_query}
    FUNCTION {query_name}({formal_spec_query_value}) RETURN SYS_REFCURSOR;
                        """

                        package_body += f"""
    FUNCTION {query_name}({formal_spec_query_value}) RETURN SYS_REFCURSOR IS

    BEGIN
        -- TODO : Implement method body
        RETURN NULL;    
    END {query_name};
                        """
                    else:
                        package_content += f"""
    {formatted_description_query}
    {declare_record_query}
    FUNCTION {query_name} RETURN SYS_REFCURSOR;
                                            """

                        package_body += f"""
    FUNCTION {query_name} RETURN SYS_REFCURSOR IS

    BEGIN
        -- TODO : Implement method body
        RETURN NULL;    
    END {query_name};
                                            """

                file_content = package_header + package_content + package_body + package_end

                with open(file_convert, "w", encoding="utf-8") as sql_file:
                    sql_file.write(file_content)

            return jsonify({'status': 'success', 'message': 'Check File successful!', 'data': "data"})

    except Exception as e:
        # Xảy ra lỗi
        print("[start_convert_cls] error : " + str(e))
        logging.error(" [start_convert_cls] error : " + str(e))
        return jsonify({'status': 'success', 'message': 'Check File error!', 'data': str(e)})


def convert_query_parameter(input_str):
    elements = input_str.split(',')

    output_str1 = ""
    # Duyệt qua từng phần tử và chuyển đổi
    output_elements = []
    last_index = len(elements) - 1
    for index, element in enumerate(elements):
        # Tách tên biến và kiểu dữ liệu
        parts = element.split(':')
        if len(parts) == 2:
            var_name, var_type = parts
            var_name = var_name.strip()
            if var_name.upper() in oracle_keywords:
                var_name = "\"" + var_name + "\""
            if '=' in var_type:
                var_type_value = convert_data_type_file(var_type.split('=')[0])
                var_type_value += " DEFAULT " + var_type.split('=')[1]
            else:
                var_type_value = convert_data_type_file(var_type)
                if var_type_value == "VARCHAR2":
                    var_type_value = "VARCHAR2(4000)"

            # Tạo định dạng đầu ra cho tham số
            if index == last_index:
                output_var = f"{var_name} {var_type_value}"
            else:
                output_var = f"{var_name} {var_type_value},"

            output_elements.append(output_var)

        elif len(parts) == 3:
            var_name, var_type, var_comment = parts
            var_name = var_name.strip()
            if var_name.upper() in oracle_keywords:
                var_name = "\"" + var_name + "\""
            if '=' in var_type:
                if "SCALE".upper() in var_type.upper():
                    var_type_value = convert_data_type_file(var_type.split('(')[0])
                else:
                    var_type_value = convert_data_type_file(var_type.split('=')[0])
                    var_type_value += " DEFAULT " + var_type.split('=')[1]
            else:
                var_type_value = convert_data_type_file(var_type)
                if var_type_value == "VARCHAR2":
                    var_type_value = "VARCHAR2(4000)"

            # Tạo định dạng đầu ra cho tham số
            if element == elements[-1]:
                output_var = f"{var_name} {var_type_value} --{var_comment}"
            else:
                output_var = f"{var_name} {var_type_value}, --{var_comment}"
            output_elements.append(output_var)

    # Kết hợp các phần tử lại với nhau và ngăn cách bằng dấu phẩy
    output_str = '\n\t\t'.join(output_elements)
    return output_str


def convert_formal_spec(input_str):
    # Tách các phần tử bằng dấu phẩy
    elements = input_str.split(',')

    # Duyệt qua từng phần tử và chuyển đổi
    output_elements = []
    for element in elements:
        # Tách tên biến và kiểu dữ liệu
        parts = element.split(':')
        if len(parts) == 2:
            var_name, var_type = parts
            if var_name.upper() in oracle_keywords:
                var_name = "\"" + var_name + "\""
            if '=' in var_type:
                var_type_value = convert_data_type_file(var_type.split('=')[0])
                default_value = var_type.split('=')[1].replace("\"", "\'")
                if default_value == "''":
                    default_value = "NULL"
                var_type_value += " DEFAULT " + default_value
            else:
                var_type_value = convert_data_type_file(var_type)
            # Xác định kiểu của tham số đầu ra
            var_in_out = "IN"
            if '&' in var_name:
                var_name = var_name.replace('&', '').strip()
                var_in_out = "OUT"

            # Tạo định dạng đầu ra cho tham số
            output_var = f"{var_name} {var_in_out} {var_type_value}"
            output_elements.append(output_var)
        elif len(parts) == 3:
            var_name, var_type, var_data = parts
            if var_name.upper() in oracle_keywords:
                var_name = "\"" + var_name + "\""
            if '=' in var_type:
                var_type_value = convert_data_type_file(var_type.split('=')[0])
                var_type_value += " DEFAULT " + var_type.split('=')[1]
            else:
                var_type_value = convert_data_type_file(var_type)
                if var_type_value == "VARCHAR2":
                    var_type_value = "VARCHAR2(4000)"

            # Tạo định dạng đầu ra cho tham số
            output_var = f"{var_name} {var_type_value}"
            output_elements.append(output_var)

    # Kết hợp các phần tử lại với nhau và ngăn cách bằng dấu phẩy
    output_str = ', '.join(output_elements)
    return output_str


def convert_data_type_file(data_type):
    if '%String' == data_type or '%Library.String' == data_type:
        data_type = "VARCHAR2"
    elif '%Binary' == data_type or '%Library.Binary' == data_type:
        data_type = "STRING_ARRAY"
    elif '%Boolean' == data_type or '%Library.Boolean' == data_type:
        data_type = "NUMBER"
    elif '%Integer' == data_type or '%Library.Integer' == data_type:
        data_type = "NUMBER"
    elif '%List' == data_type or '%Library.List' == data_type:
        data_type = "STRING_ARRAY"
    elif '%Status' == data_type or '%Library.Status' == data_type:
        data_type = "NUMBER"
    elif '%Double' == data_type or '%Library.Double' == data_type:
        data_type = "NUMBER"
    elif '%Time' == data_type or '%Library.Time' == data_type:
        data_type = "TIMESTAMP"
    elif '%Timestamp' == data_type or '%Library.Timestamp' == data_type:
        data_type = "TIMESTAMP"
    elif '%Numeric' == data_type or '%Library.Numeric' == data_type:
        data_type = "NUMBER"
    elif '%Currency' == data_type or '%Library.Currency' == data_type:
        data_type = "NUMBER"
    elif '%Float' == data_type or '%Library.Float' == data_type:
        data_type = "NUMBER"

    # truong hop dac biet
    elif 'Com.UpdateInfo' == data_type:
        data_type = "COM_UPDATE_INFO"
    return data_type


def convert_data_type_table(data_type, param):
    ########
    if '%String' == data_type:
        data_type = "BIGINT"
    elif '%Bigint' == data_type:
        data_type = "NUMBER(19)"
    elif '%Binary' == data_type:
        data_type = "BLOB"
    elif '%Boolean' == data_type:
        data_type = "NUMBER(1)"
    elif '%Date' == data_type:
        data_type = "DATE"
    elif '%Integer' == data_type:
        data_type = "NUMBER(10)"
    ########
    elif '%Decimal' == data_type:
        data_type = "DATE"
    elif '%Double' == data_type:
        data_type = "BINARY_DOUBLE"
    elif '%Time' == data_type:
        data_type = "TIMESTAMP"
    elif '%Timestamp' == data_type:
        data_type = "TIMESTAMP"


@actions.route('/start-convert-mac', methods=['POST', 'GET'])
def start_convert_mac():
    try:
        if request.method == 'POST':
            print("[start-convert-mac]")
            logging.info("#### [start-convert-mac] ####")
            files = request.files.getlist('filepond')

            for xml_file in files:
                data = xml_file.getvalue()
                content = xml.dom.minidom.parseString(data)
                # print(content.toprettyxml(newl=''))

                mac_node = content.getElementsByTagName("Routine")[0]
                mac_name = mac_node.getAttribute("name")

                # Loại bỏ dấu "."
                input_str = mac_name.replace(".", "")
                # Thêm dấu "_" trước chữ in hoa
                output_str = ''.join(['_' + c if c.isupper() else c for c in input_str]).lstrip('_')
                # Thêm "_MAC" vào cuối
                output_str += "_MAC"
                file_convert_name = output_str.upper()
                file_convert = "MAC_RESULT/" + file_convert_name + ".sql"

                isExist = os.path.exists("MAC_RESULT")
                if not isExist:
                    os.makedirs("MAC_RESULT")

                pattern_method = r'\n([\w.]+)\(([^)]*)(?<!\/\/)\)\s*(Public|Private|public|private|PUBLIC|PRIVATE|)\s*{([\s\S]*?)'
                # Tìm tag <Routine> và lấy nội dung CDATA bên trong
                routine_cdata = content.getElementsByTagName("Routine")[0].firstChild.data

                # trước khi xử lý remove dòng có comment #;
                code_lines = routine_cdata.split('\n')
                pattern_check_comment = r'^\s*\#\;'
                processed_code = []
                result_code_after_format = ""
                for line in code_lines:
                    if re.findall(pattern_check_comment, line.strip()):
                        continue
                    else:
                        result_code_after_format += line + "\n"

                routine_cdata = result_code_after_format
                methods = re.findall(pattern_method, routine_cdata)

                # remove #include, #define of routine_cdata for find pattern javadoc
                new_routine_cdata = ""
                code_lines_new = routine_cdata.split('\n')
                for line in code_lines_new:
                    if re.findall(pattern_check_comment, line.strip()):
                        continue
                    elif ("#Include".upper() in line.upper()) or ("#Define".upper() in line.upper()):
                        continue
                    else:
                        new_routine_cdata += line + "\n"

                pattern_method_javadoc = r'(\/\/\/\s*(.*?)\s*(<BR>|)[\s\S]*?\n)([\w.]+)\((([^)【】]+)|)\)\s*(Public|Private|public|private|PUBLIC|PRIVATE|)\s*{([\s\S]*?)'
                methods_javadoc = re.findall(pattern_method_javadoc, new_routine_cdata)

                pattern_include = r'#Include\s+(\S+)'
                # Sử dụng re.findall để tìm tất cả các #Include trong đoạn văn bản
                includes = re.findall(pattern_include, routine_cdata, re.IGNORECASE)
                include_list = ""
                if includes:
                    include_list += """/*******************************************************
     *  DECLARE INCLUDE LIST: Where constants should be
     *******************************************************/                   
    INCLUDE_LIST STRING_ARRAY := STRING_ARRAY("""
                    pattern_storage = '\.storage'
                    for include in includes:
                        if not re.search(pattern_storage, include, re.IGNORECASE):
                            include_list += f"""'{include}',"""
                    # Loại bỏ dấu "," cuối cùng và thêm dấu ");"
                    if include_list.endswith(","):
                        include_list = include_list[:-1] + ');'
                    else:
                        include_list += ");"
                else:
                    include_list += """
    /*******************************************************
     *  DECLARE INCLUDE LIST: Where constants should be
     *******************************************************/                   
    INCLUDE_LIST STRING_ARRAY := STRING_ARRAY();"""

                pattern_constant = r'#Define\s+(\w+)\s+"?([^"\n]+)"?\s*'
                # Sử dụng re.findall để tìm tất cả các #Define trong đoạn văn bản
                find_defines = re.findall(pattern_constant, routine_cdata, re.IGNORECASE)
                output_constants = """
    /*******************************************************
     *  DECLARE CONSTANTS: Constants using in this package
     *******************************************************/  
                """
                if find_defines:
                    for name, value in find_defines:
                        output_constants += f"""                 
    {name} VARCHAR2(150) := '{value}';"""
                output_constants += f"""\n
    ---------------- END DECLARE CONSTANTS -----------------"""

                package_header = f"CREATE OR REPLACE PACKAGE {file_convert_name} AS "
                package_content = f"""

    /*****************************************************
     *  PACKAGE NAME: Use for replacement $ZNAME in Caché
     *****************************************************/
    PACKAGE_NAME VARCHAR2(150) := '{file_convert_name}'; """
                if include_list != "":
                    package_content += f"""
    {include_list}
                    """
                if output_constants:
                    package_content += f"""
    {output_constants}
                    """

                package_content += f"""
    /*******************************************************
     *  DECLARE METHODS: Declare function or procedure here
     *******************************************************/
                """

                package_body = f"""
    ----------------- END DECLARE METHODS -------------------
END {file_convert_name};
/
CREATE OR REPLACE PACKAGE BODY {file_convert_name} AS """
                package_body += f"""

    /*******************************************************
     *  IMPLEMENTATION: Implement logic here
     *******************************************************/            
                                            """
                # mrd methods -> methods ALL and not javadoc
                method_exist_javadoc_name = []
                for method in methods_javadoc:
                    method_exist_javadoc_name.append(method[3])
                    method_comment = method[0]
                    method_name = method[3]
                    method_params = method[4]
                    method_access = "RETURN VARCHAR2"
                    # Tách các phần từ trong chuỗi đầu vào
                    input_list = method_params.split(',')
                    output_list = []
                    array_default_value = []
                    # Lặp qua danh sách các phần tử và thêm phần tử chuyển đổi vào danh sách mới
                    for item in input_list:
                        item = item.strip()
                        check_default_out_param = False
                        if '=' in item:
                            if "..." in item:
                                item = item.replace("...", "")
                                param_name = item.split('=')[0].strip()
                                if param_name.upper() in oracle_keywords:
                                    param_name = "\"" + param_name + "\""
                                default_value = item.split('=')[1].replace("\"", '\'').strip()
                                if default_value == "\'\'":
                                    default_value = "NULL"

                                if "po" in item:
                                    check_default_out_param = True
                                    parameter_output = param_name + " OUT STRING_ARRAY"
                                    output_list.append(f'{parameter_output}')
                                elif "pInput" in item:
                                    check_default_out_param = True
                                    param_default = " DEFAULT" + default_value.replace("\"", '\'')
                                    parameter_output = param_name + " IN STRING_ARRAY " + param_default
                                    output_list.append(f'{parameter_output}')
                                else:
                                    check_default_out_param = True
                                    param_default = " DEFAULT" + default_value.replace("\"", '\'')
                                    parameter_output = param_name + " IN STRING_ARRAY " + param_default
                                    output_list.append(f'{parameter_output}')
                            else:
                                param_name = item.split('=')[0].strip()
                                if param_name.upper() in oracle_keywords:
                                    param_name = "\"" + param_name + "\""
                                default_value = item.split('=')[1].replace("\"", '\'').strip()
                                if default_value == "\'\'":
                                    default_value = "NULL"

                                param_default = "DEFAULT " + default_value.strip()
                                if "po" in item:
                                    parameter_output = param_name + " OUT VARCHAR2"
                                    array_default_value.append((param_name, default_value))
                                    output_list.append(f'{parameter_output}')
                                elif "pInput" in item:
                                    parameter_output = param_name + " IN VARCHAR2 " + param_default
                                    output_list.append(f'{parameter_output}')
                                else:
                                    # sửa lại format in ra

                                    # lưu trữ lại param và default value
                                    if "$$$" in default_value:
                                        constant = default_value[3:]
                                        default_value = f"COMMON.GET_CONSTANT('{constant}', INCLUDE_LIST)"
                                    parameter_output = param_name + " IN VARCHAR2 DEFAULT " + default_value
                                    output_list.append(f'{parameter_output}')
                        elif item == '':
                            print("mrd")
                        else:
                            if "..." in item:
                                item = item.replace("...", "")
                                if "po" in item:
                                    output_list.append(f'{item} OUT STRING_ARRAY')
                                else:
                                    output_list.append(f'{item} IN STRING_ARRAY')
                            else:
                                if "po" in item:
                                    output_list.append(f'{item} OUT VARCHAR2')
                                elif "pInput" in item:
                                    output_list.append(f'{item} IN VARCHAR2')
                                else:
                                    if item.upper() in oracle_keywords:
                                        item = "\"" + item + "\""
                                    output_list.append(f'{item} IN VARCHAR2')

                    output_params = ', '.join(output_list)
                    # chuyển đổi comment :
                    method_comment_mac = "/**\n"
                    lines = method_comment.split('\n')
                    for line in lines:
                        if line.strip() != "":
                            method_comment_mac += f"     * {line}\n"
                    method_comment_mac += "    **/"
                    method_comment_mac = method_comment_mac.replace("<BR>", "").replace("///", "")
                    if output_params == '':
                        method_content = "FUNCTION " + method_name + " " + method_access
                    else:
                        method_content = "FUNCTION " + method_name + "(" + output_params + ") " + method_access
                    package_content += f"""
    {method_comment_mac}
    {method_content};       
                                    """
                    output_default_value = ""
                    for item_set_value in array_default_value:
                        item_name = item_set_value[0]
                        item_value = item_set_value[1]
                        output_default_value += item_name + " := " + item_value + ";\n"

                    package_body += f"""
    {method_content} IS   
    BEGIN"""
                    if output_default_value == "":
                        package_body += f"""
        -- TODO : Implement method body
        RETURN NULL;  
    END {method_name};
                """
                    else:
                        package_body += f"""
        {output_default_value}
        -- TODO : Implement method body
        RETURN NULL;  
    END {method_name};
                                    """
                package_end = f"""
    ----------------- END IMPLEMENTATION -------------------
END {file_convert_name};
/
                """

                # end for method_javadoc
                # duyệt thêm các method mà không có javadoc
                for method in methods:
                    method_name1 = method[0]
                    if method_name1 == "SetPrintJyokenCycle":
                        print("mrd")
                    method_params1 = method[1]
                    method_access1 = "RETURN VARCHAR2"
                    if method_name1 not in method_exist_javadoc_name:
                        # Tách các phần từ trong chuỗi đầu vào
                        input_list1 = method_params1.split(',')
                        output_list1 = []
                        # Lặp qua danh sách các phần tử và thêm phần tử chuyển đổi vào danh sách mới

                        for item in input_list1:
                            item = item.strip()
                            if '=' in item:
                                if "..." in item:
                                    item = item.replace("...", "")
                                param_name = item.split('=')[0].strip()
                                if param_name.upper() in oracle_keywords:
                                    param_name = "\"" + param_name + "\""
                                param_default = (item.split('=')[1].replace("\"", '\'')).strip()
                                if "po" in item:
                                    parameter_output = param_name + " OUT VARCHAR2 DEFAULT " + param_default
                                    output_list1.append(f'{parameter_output}')
                                else:
                                    if "''" in param_default:
                                        param_default = "NULL"
                                    parameter_output = param_name + " IN VARCHAR2" + " DEFAULT " + param_default
                                    output_list1.append(f'{parameter_output}')
                            elif item == '':
                                print("function không có param")
                            else:
                                if "..." in item:
                                    item = item.replace("...", "")
                                if "po" in item:
                                    output_list1.append(f'{item} OUT VARCHAR2')
                                else:
                                    if item.upper() in oracle_keywords:
                                        item = "\"" + item + "\""
                                    output_list1.append(f'{item} IN VARCHAR2')

                        output_params = ', '.join(output_list1)
                        array_re_format_param = output_params.split(",")
                        array_new = []
                        if array_re_format_param:
                            array_default_value_method = []
                            for item_new_value in array_re_format_param:
                                if ("OUT" in item_new_value) and ("DEFAULT" in item_new_value):
                                    # sửa lại format in ra
                                    item_out_value = item_new_value.split("DEFAULT")[0]
                                    # lưu trữ lại param và default value
                                    new_param_name = item_new_value.split("OUT")[0]
                                    default_value = item_new_value.split("DEFAULT")[1]
                                    if "''" in default_value:
                                        default_value = "NULL"
                                    elif "$$$" in default_value:
                                        constant = default_value[3:]
                                        default_value = f"COMMON.GET_CONSTANT('{constant}', INCLUDE_LIST)"

                                    array_default_value_method.append((new_param_name, default_value))
                                elif ("IN" in item_new_value) and ("DEFAULT" in item_new_value):
                                    new_param_name = item_new_value.split("IN")[0]
                                    default_value = item_new_value.split("DEFAULT")[1]
                                    if "$$$" in default_value:
                                        constant = default_value[3:]
                                        default_value = f"COMMON.GET_CONSTANT('{constant}', INCLUDE_LIST)"
                                    item_out_value = new_param_name + " IN VARCHAR2 DEFAULT " + default_value
                                else:
                                    item_out_value = item_new_value
                                array_new.append(item_out_value)

                            # Kết hợp các phần tử lại với nhau và ngăn cách bằng dấu phẩy
                            output_str_new_param_value = ','.join(array_new)
                            output_params = output_str_new_param_value  # mrd

                        output_default_value_method_mac = ""
                        for item_set_value_method in array_default_value_method:
                            item_name = item_set_value_method[0]
                            item_value = item_set_value_method[1]
                            output_default_value_method_mac += item_name + ":= " + item_value + ";\n"

                        if output_params == '':
                            method_content1 = "FUNCTION " + method_name1 + " " + method_access1
                            package_content += f"""
    {method_content1};       
                                                """
                            package_body += f"""
    {method_content1} IS   
    BEGIN
        -- TODO : Implement method body
        RETURN NULL;  
    END {method_name1};
                                            """


                        else:
                            method_content1 = "FUNCTION " + method_name1 + "(" + output_params + ") " + method_access1
                            package_content += f"""
    {method_content1};       
                                               """

                            package_body += f"""
    {method_content1} IS   
    BEGIN
                                        """
                            if output_default_value_method_mac == "":
                                package_body += f"""            
        -- TODO : Implement method body
        RETURN NULL;  
    END {method_name1};
                                            """
                            else:
                                package_body += f"""     
        {output_default_value_method_mac}                           
        -- TODO : Implement method body
        RETURN NULL;  
    END {method_name1};
                                            """
                file_content = package_header + package_content + package_body + package_end

                with open(file_convert, "w", encoding="utf-8") as sql_file:
                    sql_file.write(file_content)

            return jsonify({'status': 'success', 'message': 'Check File successful!', 'data': "data"})

    except Exception as e:
        # Xảy ra lỗi
        print("[start_convert_mac] error : " + str(e))
        logging.error(" [start_convert_mac] error : " + str(e))
        return jsonify({'status': 'success', 'message': 'Check File error!', 'data': str(e)})


@actions.route('/convert_editor', methods=['POST'])
def convert_editor():
    print("[convert_editor] : ")
    logging.info("#### [convert_by_editor] ####")
    try:
        if request.method == 'POST':
            from_code = request.form['code-editor-1']
            conversion_rules_file_path = "./config/convert_cache_to_oracle_rules.txt"
            conversion_rules = read_conversion_rules_from_file(conversion_rules_file_path)

            # convert _ -> ||
            to_code_temp = re.sub(r'_', r'||', from_code)

            # Convert comment /* */ multiline
            pattern_comment_mutil_line = r'(\/\*\s*([^*]*)\s*\n\*\/)'
            matchs_comment_mutil_line = re.findall(pattern_comment_mutil_line, to_code_temp)
            if matchs_comment_mutil_line:
                for match_comment_mutil_line in matchs_comment_mutil_line:
                    to_code_temp = to_code_temp.replace(match_comment_mutil_line[0], "")  # mrd

            # Convert comment #; /// ;
            to_code_temp = convert_comment_pattern(to_code_temp)

            # convert if else :
            to_code_temp = process_code(to_code_temp)

            # check $$[1] : $$MethodName^RoutineName(param1, param2,...) ex : $$GetMotherInfoLog^Com.MotherUpdateLog(SyohinSeq, piDate, CheckCd)
            pattern_dola_dola_1 = r'\$\$(\w+)\^(\w+)\.(\w+)\((.*?)\)'
            # Tìm các kết hợp phù hợp trong chuỗi và thực hiện chuyển đổi
            to_code_temp = convert_from_pattern(pattern_dola_dola_1, to_code_temp)

            # check $$[1] : $$MethodName^RoutineName(param1, param2,...) ex : $$GetMotherInfoLog^MotherUpdateLog(SyohinSeq, piDate, CheckCd)
            pattern_dola_dola_1_2 = r'\$\$(\w+)\^(\w+)\((.*?)\)'
            # Tìm các kết hợp phù hợp trong chuỗi và thực hiện chuyển đổi
            to_code_temp = convert_from_pattern_2(pattern_dola_dola_1_2, to_code_temp)

            # check $$ [2] $$MethodName(param1, param2,...)
            # input -> $$MethodName(param1, param2,.param3,.param4) -> $$MethodName(param1, param2, param3, param4)
            pattern_dola_dola_2 = r'\$\$([^\s(\^@]+)\(([^)]+)'
            to_code_temp = convert_from_pattern_dola_dola_2(pattern_dola_dola_2, to_code_temp)

            # check Do[3] : Do MethodName^RoutineName(param, ...) -> ROUTINE_NAME_MAC.MethodName(param1, param2,...)
            pattern_do_3 = r'Do (\w+)\^(\w+)\.(\w+)\((.*?)\)'
            # Tìm các kết hợp phù hợp trong chuỗi và thực hiện chuyển đổi
            matches_do_3 = re.findall(pattern_do_3, from_code.strip())
            if matches_do_3:
                for match_do_3 in matches_do_3:
                    m_do3_function = match_do_3[0]
                    m_do3_package = match_do_3[1].upper()
                    m_do3_routine = match_do_3[2]
                    m_do3_param = match_do_3[3]
                    input_str_do3 = "Do " + match_do_3[0] + "^" + match_do_3[1] + "." + match_do_3[2] + "(" + \
                                    match_do_3[
                                        3] + ")"
                    m_do3_routine = ''.join(['_' + c if c.isupper() else c for c in m_do3_routine]).lstrip('_')
                    m_do3_routine = m_do3_routine.upper()
                    # kiểm tra xem param có . không, nếu có remove đi
                    m_do3_param = re.sub(r'\.', '', m_do3_param)
                    output_str_do_3 = m_do3_package + "_" + m_do3_routine + "_MAC." + m_do3_function + "(" + m_do3_param + ")"

                    to_code_temp = to_code_temp.replace(input_str_do3, output_str_do_3)

            pattern_do_4 = r'(Do\s*##class)\(([^)]*)\).([^(]*)([^\n]*)'
            matches_do_4 = re.findall(pattern_do_4, from_code.strip())
            if matches_do_4:
                for match_do_4 in matches_do_4:
                    m_do4_class_name = match_do_4[1]
                    m_do4_method_name = match_do_4[2]
                    m_do4_param = match_do_4[3]

                    if "." in m_do4_class_name:
                        m_do4_class_name = m_do4_class_name.replace(".", "")
                    # Thêm dấu "_" trước chữ in hoa cua ClassName
                    output_class_name = ''.join(['_' + c if c.isupper() else c for c in m_do4_class_name]).lstrip('_')
                    output_class_name = output_class_name.upper() + "_CLS"
                    output_str_do_4 = output_class_name + "." + m_do4_method_name + m_do4_param
                    input_str_do4 = match_do_4[0] + "(" + match_do_4[1] + ")" + "." + m_do4_method_name + m_do4_param

                    to_code_temp = to_code_temp.replace(input_str_do4, output_str_do_4)

            # check to_code có chứa tên hàm để replace:
            pattern_func = r'\$\$([A-Za-z0-9]+)\^(\w+)\.([A-Za-z0-9]+)\(([^)]+)\)'
            matches = re.findall(pattern_func, to_code_temp.strip())
            if matches:
                for match in matches:
                    input_str = "$$" + match[0] + "^" + match[1] + "." + match[2] + "(" + match[3] + ")"
                    m_function = match[0]
                    m_package = match[1]
                    m_routine = match[2]
                    m_param = match[3]
                    # Thêm dấu "_" trước chữ in hoa
                    output_str = ''.join(['_' + c if c.isupper() else c for c in match[2]]).lstrip('_')
                    # _MAC vào cuối và viết Hoa
                    output_str = (match[1].upper() + "_" + output_str + "_MAC").upper()
                    # trả lại chuỗi in ra :
                    output_str = output_str + "." + match[0].upper() + "(" + match[3] + ")"

                    # Replace đoạn pattern bằng chuỗi output_str
                    to_code_temp = to_code_temp.replace(input_str, output_str)

            to_code = convert_cache_to_oracle(to_code_temp, conversion_rules)

            return render_template('convert-code.html', from_code=from_code, to_code=to_code)

    except Exception as e:
        flash('Error :' + str(e), 'danger')
        print("[convert_editor] error : " + str(e))
        logging.error(" [convert_editor] error : " + str(e))
        return redirect(url_for('actions.convert_code'))


# convert comment
def convert_comment_pattern(from_code):
    pattern1 = r'(\#\;)([^\n]+)'
    pattern2 = r'(\/\/)([^\n]+)'
    pattern3 = r'(\;)([^\n}]+)'
    to_code_temp = from_code

    # matchs1 = re.findall(pattern1, from_code.strip())
    # for match1 in matchs1:
    #     input_str1 = match1[0] + match1[1]
    #     output_str1 = "--" + match1[1]
    #     to_code_temp = to_code_temp.replace(input_str1, output_str1)

    matchs2 = re.findall(pattern2, to_code_temp.strip())
    for match2 in matchs2:
        input_str2 = match2[0] + match2[1]
        output_str2 = "--" + match2[1]
        to_code_temp = to_code_temp.replace(input_str2, output_str2)

    # matchs3 = re.findall(pattern3, to_code_temp.strip())
    # for match3 in matchs3:
    #     input_str3 = match3[0] + match3[1]
    #     output_str3 = "--" + match3[1]
    #     to_code_temp = to_code_temp.replace(input_str3, output_str3)

    return to_code_temp


# check $$[1] : $$MethodName^RoutineName(param1, param2,...)
def convert_from_pattern(pattern, from_code):
    print("###[convert_from_pattern]###")
    # Tìm các kết hợp phù hợp trong chuỗi và thực hiện chuyển đổi
    to_code_temp = from_code
    matchs = re.findall(pattern, from_code.strip())
    for match in matchs:
        m_function = match[0]
        m_package = match[1].upper()
        m_routine = match[2]
        m_param = match[3]
        input_str = match[0] + "^" + match[1] + "." + match[2] + "(" + match[3] + ")"
        m_routine = ''.join(['_' + c if c.isupper() else c for c in m_routine]).lstrip('_')
        m_routine = m_routine.upper()
        # kiểm tra xem param có . không, nếu có remove đi
        m_param = re.sub(r'\.', '', m_param)
        output_str = m_package + "_" + m_routine + "_MAC." + m_function + "(" + m_param + ")"

        to_code_temp = to_code_temp.replace(input_str, output_str)
    return to_code_temp


def convert_from_pattern_2(pattern, from_code):
    print("###[convert_from_pattern]###")
    # Tìm các kết hợp phù hợp trong chuỗi và thực hiện chuyển đổi
    to_code_temp = from_code
    matchs = re.findall(pattern, from_code.strip())
    for match in matchs:
        m_function = match[0]
        m_routine = match[1]
        m_param = match[2]
        input_str = match[0] + "^" + match[1] + "(" + match[2] + ")"
        m_routine = ''.join(['_' + c if c.isupper() else c for c in m_routine]).lstrip('_')
        m_routine = m_routine.upper()
        # kiểm tra xem param có . không, nếu có remove đi
        m_param = re.sub(r'\.', '', m_param)
        output_str = m_routine + "_MAC." + m_function + "(" + m_param + ")"

        to_code_temp = to_code_temp.replace(input_str, output_str)
    return to_code_temp


# check $$[2] : $$MethodName(param1, param2,.param3, .param4)
def convert_from_pattern_dola_dola_2(pattern, from_code):
    print("###[convert_from_pattern]###")
    # Tìm các kết hợp phù hợp trong chuỗi và thực hiện chuyển đổi
    to_code_temp = from_code
    matchs = re.findall(pattern, from_code.strip())
    for match in matchs:
        m_function = match[0]
        m_param = match[1]
        input_str = "$$" + match[0] + "(" + match[1] + ")"
        # kiểm tra xem param có . không, nếu có remove đi
        m_param = re.sub(r'\.', '', m_param)
        output_str = m_function + "(" + m_param + ")"
        to_code_temp = to_code_temp.replace(input_str, output_str)
    return to_code_temp


def read_conversion_rules_from_file(file_path):
    with open(file_path, 'r') as file:
        conversion_rules = [line.strip().split('|||') for line in file.readlines()]
    return conversion_rules


def convert_cache_to_oracle(cache_code, conversion_rules):
    oracle_code = cache_code

    for rule in conversion_rules:
        cache_pattern, oracle_replace = rule
        oracle_code = re.sub(cache_pattern.strip(), oracle_replace.strip(), oracle_code, flags=re.IGNORECASE)
    # Sử dụng regex để loại bỏ xuống dòng
    oracle_code = re.sub(r'[\r]', '', oracle_code)
    return oracle_code


#########################################process if else##################################################

def process_code(source_code):
    processed_code = []
    stack = []
    pattern = r'(If|if|IF)\s*([^\n]+)\}'
    pattern2 = r'(\/\/)([^\n]+)'
    pattern3 = r'(\;)([^\n]+)'
    ## bỏ qua không migrate comment

    # check try catch để format trước
    try_catch_pattern = r'Try\s*\{([\s\S]*?)([^{}]+)\}\s*Catch([^{]+)\{([^}]+)\}'
    matches_try = re.findall(try_catch_pattern, source_code.strip(), flags=re.IGNORECASE)
    if matches_try:
        source_code = re.sub(try_catch_pattern, r'BEGIN\n  \1 \2 \nEXCEPTION\n  WHEN OTHERS THEN\n   \3\4 \nEND;',
                             source_code, flags=re.IGNORECASE)

    # for step không lồng nhau (ko lồng và không có if else do while )
    # pattern_for_step_1 = r'\s*(For)\s*(\w+)\s*\=(\w+)\:(\w+)\:([^{]*)\s*\{([\s\S]*?)\}'
    # matches_for_step_1 = re.findall(pattern_for_step_1, source_code.strip(), flags=re.IGNORECASE)
    # if matches_for_step_1:
    #     source_code = re.sub(pattern_for_step_1, r'FOR \2 IN \3..\5\n\t LOOP \n\t   \6\n\tEND LOOP;',
    #                          source_code, flags=re.IGNORECASE)

    code_lines1 = source_code.split('\n')
    new_source = []
    for line1 in code_lines1:
        if "#;" in line1:
            continue
        else:
            new_source.append(line1)
            continue
    result_new = ""
    for line_new in new_source:
        if "While".upper() in line_new.upper():
            if "||" in line_new:
                line_new = line_new.replace("||", "OR")
            if "&&" in line_new:
                line_new = line_new.replace("&&", "AND")
        result_new += line_new + "\n"

    source_code = result_new
    # For[2] lồng nhau
    source_code = checkLine(source_code)

    # For[1] lồng nhau
    source_code = checkLineFor1(source_code)

    # Do while long nhau
    source_code = checkLineDoWhile(source_code)

    # WHILE lồng nhau
    source_code = checkLineWhile(source_code)

    # check với biểu thức IF nằm trong 1 dòng và không có {}, có set:
    pattern_if_0 = r'If\s+([^\n{]+)(Set)\s*([^\n]*)'
    matches_if_0 = re.findall(pattern_if_0, source_code.strip(), flags=re.IGNORECASE)
    if matches_if_0:
        source_code = re.sub(pattern_if_0, r'IF \1 THEN \n\t    \2 \3 \n\tEND IF;\n', source_code,
                             flags=re.IGNORECASE)

    # check với biểu thức IF nằm trong 1 dòng và không có {}, có quit:
    pattern_if_1 = r'If\s+([^\n{]+)(Quit)([^\n]+)'
    matches_if_1 = re.findall(pattern_if_1, source_code.strip(), flags=re.IGNORECASE)
    if matches_if_1:
        source_code = re.sub(pattern_if_1, r'IF \1 THEN \n\t    RETURN \3; \n\tEND IF;\n', source_code,
                             flags=re.IGNORECASE)

    # check với biểu thức IF nằm trong 1 dòng và có {}:
    pattern_if_2 = r'If\s*([^{]+)\{([^}]+)\}\n'
    matches_if_2 = re.findall(pattern_if_2, source_code.strip())

    # '= $C(0) -> IS NOT NULL
    matche_pattern_char0 = r'(\'=\s*)(\$C|\$Char)(\(0\))'

    # TH1: Dùng trong các condition -> IS NULL
    # TH2: Dùng để gán giá trị -> := COMMON.C_CHAR(0)
    match_pattern_char1 = r'\s*=\s*(\$C|\$Char)\(0\)'
    match_pattern_char1_2 = r'Set\s*([^=]*)\s*=\s*\$(C|Char)\(([^)]*)\)'

    if matches_if_2:
        source_code = re.sub(pattern_if_2, r'IF \1 THEN \n\t    \2 \n\tEND IF;\n', source_code, flags=re.IGNORECASE)

    # Set piUserKey = asdasdasd , piUserKey = asdasdasd
    pattern_multi_set_2 = r'Set\s*([^=\s*]*)\s*=\s*([^,]*),\s*([^=\s*]*)\s*=\s*([^,\n]*)\s*'
    # Set piUserKey = asdasdasd , piUserKey = asdasdasd ,piUserKey = asdasdasd
    pattern_multi_set_3 = r'Set\s*([^=\s*]*)\s*=\s*([^,]*),\s*([^=\s*]*)\s*=\s*([^,]*),\s*([^=\s*]*)\s*=\s*([^,\n]*)\s*'

    # check $$$ConstantName và ko được match @$$$ConstantName@(param1, param2,...)
    pattern_dola_dola_dola_1 = r'\$\$\$([A-Za-z0-9]+)'

    code_lines = source_code.split('\n')
    for line in code_lines:
        if re.findall(pattern_multi_set_3, line.strip(), flags=re.IGNORECASE):
            line = re.sub(pattern_multi_set_3, r'\1 := \2; \3 := \4; \5 := \6;', line.strip(), flags=re.IGNORECASE)
            processed_code.append(line)
            continue
        if re.findall(pattern_multi_set_2, line.strip(), flags=re.IGNORECASE):
            line = re.sub(pattern_multi_set_2, r'\1 := \2; \3 := \4;', line.strip(), flags=re.IGNORECASE)
            processed_code.append(line)
            continue
        if re.findall(pattern_dola_dola_dola_1, line.strip(), flags=re.IGNORECASE):
            if "@$$$" not in line:
                line = re.sub(pattern_dola_dola_dola_1, r"COMMON.GET_CONSTANT('\1',INCLUDE_LIST)", line.strip(),
                              flags=re.IGNORECASE)
            processed_code.append(line)
            continue
        # if (re.findall(pattern3, line.strip())) and (("if".upper or "else".upper() or "elseif") not in line.upper()):
        if re.findall(pattern3, line.strip(), flags=re.IGNORECASE):
            line = re.sub(pattern3, r'--\2', line.strip(), flags=re.IGNORECASE)
            processed_code.append(line)
            continue
        if re.findall(matche_pattern_char0, line, flags=re.IGNORECASE):
            line = re.sub(r"'=\s*\$(C|CHAR)\(0\)", 'IS NOT NULL', line, flags=re.IGNORECASE)

        if ("If".upper() or ("While").upper() or ("ElseIf").upper() or ("QUIT:").upper()) in line.upper():
            if "||" in line:
                line = line.replace("||", "OR")
            if "&&" in line:
                line = line.replace("&&", "AND")
            if re.findall(match_pattern_char1, line, flags=re.IGNORECASE):
                if ("if".upper() in line.upper()) and ("set".upper() in line.upper()):
                    line = re.sub(match_pattern_char1_2, r'\1 := COMMON.C_CHAR(\3);', line, flags=re.IGNORECASE)
                line = re.sub(match_pattern_char1, r' IS NULL', line, flags=re.IGNORECASE)

        if ("}While".upper() in line.upper()) or ("} While".upper() in line.upper()):
            if "||" in line:
                line = line.replace("||", "OR")
            if "&&" in line:
                line = line.replace("&&", "AND")
            processed_code.append(line)
            continue
        if ("Do {".upper() or "Do{".upper() or "do {".upper() or "do{".upper()) in line.upper():
            processed_code.append(line)
            continue
        if ("IF" in line.upper() and "THEN" in line.upper()) or ("END IF;" in line.upper()):
            if "||" in line:
                line = line.replace("||", "OR")
            if "&&" in line:
                line = line.replace("&&", "AND")
            processed_code.append(line)
            continue
        if "\r" == line:
            continue
        if "#;" in line:
            continue
        if re.findall(pattern, line.strip()):
            processed_code.append(line)
            continue
        if re.findall(pattern2, line.strip()):
            processed_code.append(line)
            continue

        if ("If ".upper() in line.upper()) and ("ElseIf".upper() not in line.upper()):
            if "||" in line:
                line = line.replace("||", "OR")
            if "&&" in line:
                line = line.replace("&&", "AND")
            if "{" in line:
                if "IF " in line:
                    condition = (line).split("IF ")[1].split("{")[0]
                elif "If" in line:
                    condition = (line).split("If ")[1].split("{")[0]
                else:
                    condition = (line).split("if ")[1].split("{")[0]

                stack.append(True)  # Bắt đầu một cấp độ mới
                processed_code.append(" " * (len(stack) - 1) * 4 + f"IF {condition} THEN")
            else:
                processed_code.append(" " * len(stack) * 4 + f"IF {condition} THEN")
        elif ("Else".upper() in line.upper()) and ("ElseIf".upper() not in line.upper()):
            if "}" in line:
                if stack:
                    stack.pop()  # Kết thúc một cấp độ
                processed_code.append(" " * len(stack) * 4 + "ELSE")
                stack.append(True)  # Bắt đầu một cấp độ mới
            else:
                processed_code[-1] += " ELSE"
        elif "ElseIf".upper() in line.upper():
            if "||" in line:
                line = line.replace("||", "OR")
            if "&&" in line:
                line = line.replace("||", "AND")
            if "{" in line:
                line = line.replace("}", "")
                if "ElseIf " in line:
                    condition = (line).split("ElseIf ")[1].split("{")[0]
                elif "elseIf" in line:
                    condition = (line).split("elseIf ")[1].split("{")[0]
                elif "elseIF" in line:
                    condition = (line).split("elseIF ")[1].split("{")[0]
                elif "ElseIF" in line:
                    condition = (line).split("ElseIF ")[1].split("{")[0]
                elif "ELSEIF" in line:
                    condition = (line).split("ELSEIF ")[1].split("{")[0]
                elif "Elseif" in line:
                    condition = (line).split("Elseif ")[1].split("{")[0]
                else:
                    condition = (line).split("elseif ")[1].split("{")[0]
                processed_code.append(" " * (len(stack) - 1) * 4 + f"ELSIF {condition} ")
            else:
                processed_code.append(" " * len(stack) * 4 + f"ELSIF {condition} ")

        elif "}" in line:
            if stack:
                line = line.replace("}", "")
                stack.pop()  # Kết thúc một cấp độ
                processed_code[-1] += f"\n{line}"  # Đưa dấu "}" xuống dòng mới
                processed_code.append(" " * len(stack) * 4 + "END IF;")  # Thêm "END IF"
            else:
                processed_code.append(line)
        else:
            processed_code.append(" " * len(stack) * 4 + line)

    while stack:
        stack.pop()
        processed_code.append(" " * len(stack) * 4 + "END IF;")  # Thêm "END IF"

    result = ""
    for line in processed_code:
        result += line + "\n"
    logging.info(" [end process_code if/else]")
    return result


def checkLineWhile(source_code):
    print("checkLineWhile")
    source_code = source_code.replace("\n\n", "\n")
    pattern_while = r'While\s*([^{]*)\s*{(([\s\S]*?))\}'
    if not re.findall(pattern_while, source_code, flags=re.IGNORECASE):
        return source_code
    lines = source_code.split('\n')
    line_base = ""
    line_new = ""
    index_line = 0
    for i, line in enumerate(lines):
        if line.strip() == "":
            index_line = i
        if ("While".upper() not in line.upper()) and ("{" not in line):
            line_base += line + "\n"
            index_line = i

        elif "While".upper() in line.upper() and "{" in line:
            line_new = line  # Bắt đầu từ dòng có "While"
            for j in range(i + 1, len(lines)):
                line_new += "\n" + lines[j]  # Thêm các dòng tiếp theo vào linenew
            line_base += checkWhile(line_new)
            index_line = i
            line_base = line_base.replace("\n\n", "\n")
            break
        else:
            line_base += line + "\n"
            line_base = line_base.replace("\n\n", "\n")
            index_line = i

    if (index_line + 1 < len(lines)):
        match_pattern_while = re.findall(pattern_while, line_base, flags=re.IGNORECASE)
        if match_pattern_while:
            source_output = checkLineWhile(line_base)
            return source_output
        else:
            return line_base
    else:
        return line_base


def checkWhile(source_code):
    print("checkWhile Function")
    count_braces = 0
    inside_while = False
    lines_while = ""
    lines = source_code.split('\n')
    count = 0
    pattern_do = 'While\s*([^{]*)\s*{('
    pattern_do_loop = '([\s\S]*?)\}'
    pattern_do_loop_end = '([\s\S]*?))\}'
    line_to_end = ""
    for i, line in enumerate(lines):
        # Nếu trong một vòng DO
        if inside_while:
            if ("{" in line) and ("}" in line):
                count += 1
            elif ("{" in line) and ("}" not in line):
                count += 1
            # Tính toán số ngoặc mở và đóng
            count_braces += line.count("{")
            count_braces -= line.count("}")
            lines_while += line + "\n"
            # Nếu số ngoặc mở và đóng bằng nhau, vòng WHILE kết thúc
            if count_braces == 0:
                inside_for = False
                if count > 0:
                    for x in range(count):
                        print("While = " + str(x))
                        if x < count - 1:
                            pattern_do += pattern_do_loop
                        else:
                            pattern_do += pattern_do_loop_end
                else:
                    pattern_do += pattern_do_loop_end
                matches_pattern = re.findall(pattern_do, lines_while, flags=re.IGNORECASE)
                if matches_pattern:
                    lines_while = re.sub(pattern_do, r'WHILE \1 \n\tLOOP\n  \2 \nEND LOOP;', lines_while,
                                         flags=re.IGNORECASE)
                    for j in range(i + 1, len(lines)):
                        line_to_end += "\n" + lines[j]  # Thêm các dòng tiếp theo vào linenew
                    lines_while += "\n" + line_to_end
                return lines_while
        else:
            # Kiểm tra nếu dòng chứa vòng for
            if ("WHILE".upper() in line.upper()) and ("{" in line):
                inside_while = True
                if ("{" in line):
                    count += 1
                count_braces += line.count("{")
                count_braces -= line.count("}")
                lines_while += line + "\n"


def checkLineDoWhile(source_code):
    source_code = source_code.replace("\n\n", "\n")
    pattern_do_while = r'(Do)\s*\{([\s\S]*?)\}\s*While\s*([^\n]*)'
    if not re.findall(pattern_do_while, source_code, flags=re.IGNORECASE):
        return source_code
    lines = source_code.split('\n')
    line_base = ""
    line_new = ""
    index_line = 0
    for i, line in enumerate(lines):
        if line.strip() == "":
            index_line = i
        if ("do".upper() not in line.upper()) and ("{" not in line):
            line_base += line + "\n"
            index_line = i

        elif "Do".upper() in line.upper() and "{" in line:
            line_new = line  # Bắt đầu từ dòng có "Do"
            for j in range(i + 1, len(lines)):
                line_new += "\n" + lines[j]  # Thêm các dòng tiếp theo vào linenew
            line_base += checkDoWhile(line_new)
            index_line = i
            line_base = line_base.replace("\n\n", "\n")
            break
        else:
            line_base += line + "\n"
            line_base = line_base.replace("\n\n", "\n")
            index_line = i

    if (index_line + 1 < len(lines)):
        match_pattern_do_while = re.findall(pattern_do_while, line_base, flags=re.IGNORECASE)
        if match_pattern_do_while:
            source_output = checkLineDoWhile(line_base)
            return source_output
        else:
            return line_base
    else:
        return line_base


def checkDoWhile(source_code):
    print("checkDoWhile Function")
    count_braces = 0
    inside_do = False
    lines_do = ""
    lines = source_code.split('\n')
    line_base_for = ""
    count = 0
    pattern_do = '(Do)\s*{('
    pattern_do_loop = '[\s\S]*?}\s*While\s*[^\n]*'
    pattern_do_loop_end = ')([\s\S]*?)}\s*(While)\s*([^\n]*)'
    line_to_end = ""
    for i, line in enumerate(lines):
        # Nếu trong một vòng DO
        if inside_do:
            if ("}" in line) and ("while".upper() in line.upper()):
                count += 1
            # Tính toán số ngoặc mở và đóng
            count_braces += line.count("{")
            count_braces -= line.count("}")
            lines_do += line + "\n"
            # Nếu số ngoặc mở và đóng bằng nhau, vòng for kết thúc
            if count_braces == 0:
                inside_for = False
                if count > 0:
                    for x in range(count):
                        print("DoWhile = " + str(x))
                        if x < count - 1:
                            pattern_do += pattern_do_loop
                        else:
                            pattern_do += pattern_do_loop_end
                else:
                    pattern_do += pattern_do_loop_end
                matches_pattern = re.findall(pattern_do, lines_do, flags=re.IGNORECASE)
                if matches_pattern:
                    lines_do = re.sub(pattern_do, r'LOOP\n\t  \2\3 \n\t EXIT WHEN NOT \5 \n END LOOP;', lines_do,
                                      flags=re.IGNORECASE)
                    for j in range(i + 1, len(lines)):
                        line_to_end += "\n" + lines[j]  # Thêm các dòng tiếp theo vào linenew
                    lines_do += "\n" + line_to_end
                return lines_do
        else:
            # Kiểm tra nếu dòng chứa vòng for
            if ("do".upper() in line.upper()) and ("{" in line):
                inside_do = True
                if ("{" in line) and ("while".upper() in line):
                    count += 1
                count_braces += line.count("{")
                count_braces -= line.count("}")
                lines_do += line + "\n"


def checkLineFor1(source_code):
    source_code = source_code.replace("\n\n", "\n")
    pattern_for_1 = r'\s*For\s*\{([\s\S]*?)\}'
    if not re.findall(pattern_for_1, source_code, flags=re.IGNORECASE):
        return source_code
    lines = source_code.split('\n')
    line_base = ""
    line_new = ""
    index_line = 0
    for i, line in enumerate(lines):
        if line.strip() == "":
            index_line = i
        if ("for".upper() not in line.upper()) and ("{" not in line):
            line_base += line + "\n"
            index_line = i
        elif "If".upper() in line.upper() and "{" in line:
            print("if")
            line_base += line + "\n"
            index_line = i
        elif "for".upper() in line.upper() and "{" in line:
            line_new = line  # Bắt đầu từ dòng có "for"
            for j in range(i + 1, len(lines)):
                line_new += "\n" + lines[j]  # Thêm các dòng tiếp theo vào linenew
            line_base += checkFor1(line_new)
            index_line = i
            line_base = line_base.replace("\n\n", "\n")
            break
        else:
            line_base += line + "\n"
            line_base = line_base.replace("\n\n", "\n")
            index_line = i

    if (index_line + 1 < len(lines)):
        if re.findall(pattern_for_1, line_base, flags=re.IGNORECASE):
            source_output = checkLineFor1(line_base)
            return source_output
        else:
            return line_base
    else:
        return line_base


def checkFor1(source_code):
    print("checkFor1")
    count_braces = 0
    inside_for = False
    lines_for = ""
    lines = source_code.split('\n')
    line_base_for = ""
    count = 0
    pattern_for = '\s*For\s*\{('
    pattern_for_loop = '([\s\S]*?)\}'
    pattern_for_loop_end = '([\s\S]*?))\}'
    line_to_end = ""
    for i, line in enumerate(lines):
        # Nếu trong một vòng for
        if inside_for:
            if ("{" in line) and ("}" in line):
                count += 1
            elif ("{" in line) and ("}" not in line):
                count += 1
            # Tính toán số ngoặc mở và đóng
            count_braces += line.count("{")
            count_braces -= line.count("}")
            lines_for += line + "\n"
            # Nếu số ngoặc mở và đóng bằng nhau, vòng for kết thúc
            if count_braces == 0:
                inside_for = False
                if count > 0:
                    for x in range(count):
                        print(" x = " + str(x))
                        if x < count - 1:
                            pattern_for += pattern_for_loop
                        else:
                            pattern_for += pattern_for_loop_end
                else:
                    pattern_for += pattern_for_loop_end
                matches_pattern = re.findall(pattern_for, lines_for, flags=re.IGNORECASE)
                if matches_pattern:
                    lines_for = re.sub(pattern_for, r'LOOP\n  \1 \nEND LOOP;\n', lines_for,
                                       flags=re.IGNORECASE)
                    for j in range(i + 1, len(lines)):
                        line_to_end += "\n" + lines[j]  # Thêm các dòng tiếp theo vào linenew
                    lines_for += "\n" + line_to_end
                return lines_for
        else:
            # Kiểm tra nếu dòng chứa vòng for
            if ("For".upper() in line.upper()) and ("{" in line):
                inside_for = True
                if "{" in line:
                    count += 1
                count_braces += line.count("{")
                count_braces -= line.count("}")
                lines_for += line + "\n"


def checkLine(source_code):
    source_code = source_code.replace("\n\n", "\n")
    pattern_for_step_1 = r'\s*(For)\s*(\w+)\s*\=(\w+)\:(\w+)\:([^{]*)\s*\{([\s\S]*?)\}'
    if not re.findall(pattern_for_step_1, source_code, flags=re.IGNORECASE):
        return source_code
    lines = source_code.split('\n')
    line_base = ""
    index_line = 0
    for i, line in enumerate(lines):
        if line.strip() == "":
            index_line = i
        if ("for".upper() not in line.upper()) and ("{" not in line):
            line_base += line + "\n"
            index_line = i
        elif "If".upper() in line.upper() and "{" in line:
            print("if")
            line_base += line + "\n"
            index_line = i
        elif "for".upper() in line.upper() and "{" in line:
            line_new = line  # Bắt đầu từ dòng có "for"
            for j in range(i + 1, len(lines)):
                line_new += "\n" + lines[j]  # Thêm các dòng tiếp theo vào linenew
            line_base += checkFor(line_new)
            index_line = i
            line_base = line_base.replace("\n\n", "\n")
            break
        else:
            line_base += line + "\n"
            line_base = line_base.replace("\n\n", "\n")
            index_line = i

    if (index_line + 1 < len(lines)):
        if re.findall(pattern_for_step_1, line_base, flags=re.IGNORECASE):
            source_output = checkLine(line_base)
            return source_output
        else:
            return line_base
    else:
        return line_base


def checkFor(source_code):
    print("checkFor")
    count_braces = 0
    inside_for = False
    lines_for = ""
    lines = source_code.split('\n')
    count = 0
    pattern_for = '\s*(For)\s*(\w+)\s*\=(\w+)\:(\w+)\:([^{]*)\s*\{('
    pattern_for_loop = '([\s\S]*?)\}'
    pattern_for_loop_end = '([\s\S]*?))\}'
    line_to_end = ""
    for i, line in enumerate(lines):
        # Nếu trong một vòng for
        if inside_for:
            if ("{" in line) and ("}" in line):
                count += 1
            elif ("{" in line) and ("}" not in line):
                count += 1
            # Tính toán số ngoặc mở và đóng
            count_braces += line.count("{")
            count_braces -= line.count("}")
            lines_for += line + "\n"
            # Nếu số ngoặc mở và đóng bằng nhau, vòng for kết thúc
            if count_braces == 0:
                inside_for = False
                if count > 0:
                    for x in range(count):
                        print(" x = " + str(x))
                        if x < count - 1:
                            pattern_for += pattern_for_loop
                        else:
                            pattern_for += pattern_for_loop_end
                else:
                    pattern_for += pattern_for_loop_end
                matches_pattern = re.findall(pattern_for, lines_for, flags=re.IGNORECASE)
                if matches_pattern:
                    lines_for = re.sub(pattern_for, r'FOR \2 IN \3 .. \5\n\t LOOP \n\t   \6\nEND LOOP;\n', lines_for,
                                       flags=re.IGNORECASE)
                    for j in range(i + 1, len(lines)):
                        line_to_end += "\n" + lines[j]  # Thêm các dòng tiếp theo vào linenew
                    lines_for += "\n" + line_to_end
                return lines_for
        else:
            # Kiểm tra nếu dòng chứa vòng for
            if ("For".upper() in line.upper()) and ("{" in line):
                inside_for = True
                if "{" in line:
                    count += 1
                count_braces += line.count("{")
                count_braces -= line.count("}")
                lines_for += line + "\n"


def checkIfElse(source_code):
    print("checkIfElse")


def checkTryCatch(source_code):
    print("checkTryCatch")

# result = checkLine(source_code)
# print("mrd return : ", result)
