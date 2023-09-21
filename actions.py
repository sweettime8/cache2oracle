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
                                formatted_description += f"     * {line.strip()}\n"
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

                    # Đọc <Implementation> trong phần tử <Method> hiện tại
                    imp_value = methods[i].getElementsByTagName("Implementation").item(0)
                    if imp_value:
                        imp_value = imp_value.firstChild.nodeValue
                        pattern = r'#Include\s+(\S+)'
                        # Sử dụng re.findall để tìm tất cả các #Include trong đoạn văn bản
                        includes = re.findall(pattern, imp_value)
                        include_list = ""
                        if includes:
                            include_list += """
        -- Declare include list to know where constants should be                    
        INCLUDE_LIST STRING_ARRAY := STRING_ARRAY("""
                            pattern_storage = '\.storage'
                            for include in includes:
                                if not re.search(pattern_storage, include):
                                    include_list += f"""'{include}',"""
                            # Loại bỏ dấu "," cuối cùng và thêm dấu ");"
                            include_list = include_list[:-1] + ');'

                        pattern_constant = r'#Define\s+(\w+)\s+"?([^"\n]+)"?\s*'
                        # Sử dụng re.findall để tìm tất cả các #Define trong đoạn văn bản
                        find_defines = re.findall(pattern_constant, imp_value)
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

                        if check_match:
                            # là function
                            package_content += f"""
    {formatted_description}
    FUNCTION {method_name}({formal_spec_value}) RETURN {return_type_value};    
                            """
                            package_body += f"""
    FUNCTION {method_name}({formal_spec_value}) RETURN {return_type_value} IS  
        {include_list}
        {output_constants}
        /* todo */
    BEGIN
        /* todo */ 
        RETURN NULL;   
    END {method_name};
                            """
                        else:
                            # là procedure
                            package_content += f"""
    {formatted_description}                        
    PROCEDURE {method_name}({formal_spec_value}) ;        
                                                    """
                            package_body += f"""
    PROCEDURE {method_name}({formal_spec_value}) IS  
        {include_list}\n
        {output_constants}
        /* todo */
    BEGIN
        /* todo */  
    END {method_name};
                            """

                #### end for method

                #### Start for query
                for i in range(len(query_cls)):
                    query_name = query_cls[i].getAttribute("name")
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
                                formatted_description_query += f"     * {line.strip()}\n"
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

                    declare_record_query = f"TYPE table{query_name} IS TABLE OF record{query_name}Tmp;"
                    declare_record_query += f"""
    TYPE record{query_name}Tmp IS RECORD (
         {parameter_query_query_value}
    ) ;
                    """

                    package_content += f"""
    {formatted_description_query}
    {declare_record_query}
    FUNCTION {query_name}({formal_spec_query_value}) RETURN SYS_REFCURSOR;
                        """

                    package_body += f"""
    FUNCTION {query_name}({formal_spec_query_value})  RETURN SYS_REFCURSOR IS

    /* todo */
    BEGIN
    /* todo */
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
    for element in elements:
        # Tách tên biến và kiểu dữ liệu
        parts = element.split(':')
        if len(parts) == 2:
            var_name, var_type = parts
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

        elif len(parts) == 3:
            var_name, var_type, var_comment = parts
            if '=' in var_type:
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
    output_str = '\n         '.join(output_elements)
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
            if '=' in var_type:
                var_type_value = convert_data_type_file(var_type.split('=')[0])
                var_type_value += " DEFAULT " + var_type.split('=')[1]
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

                pattern_method = r'([\w.]+)\(([^)]*)(?<!\/\/)\)\s*(Public|Private|public|private|PUBLIC|PRIVATE|)\n\{'
                # Tìm tag <Routine> và lấy nội dung CDATA bên trong
                routine_cdata = content.getElementsByTagName("Routine")[0].firstChild.data
                methods = re.findall(pattern_method, routine_cdata)

                pattern_include = r'#Include\s+(\S+)'
                # Sử dụng re.findall để tìm tất cả các #Include trong đoạn văn bản
                includes = re.findall(pattern_include, routine_cdata)
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
                find_defines = re.findall(pattern_constant, routine_cdata)
                output_constants = """
     /*******************************************************
     *  DECLARE CONSTANTS: Constants using in this package
     *******************************************************/  
                """
                if find_defines:
                    for name, value in find_defines:
                        output_constants += f"""                 
    {name} VARCHAR2(150) := '{value}';"""

                package_header = f"CREATE OR REPLACE PACKAGE {file_convert_name} AS "
                package_content = f"""

    /*****************************************************
     *  PACKAGE NAME: Use for replacement $ZNAME in Caché
     *****************************************************/
     PACKAGE_NAME VARCHAR2(150) := '{file_convert_name}'; """
                if include_list:
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

                for method in methods:
                    method_name = method[0]
                    method_params = method[1]
                    # method_access = method[2]
                    method_access = "RETURN VARCHAR2 "
                    # Tách các phần từ trong chuỗi đầu vào
                    input_list = method_params.split(', ')
                    output_list = []
                    # Lặp qua danh sách các phần tử và thêm phần tử chuyển đổi vào danh sách mới
                    for item in input_list:
                        if "po" in item:
                            output_list.append(f'{item} OUT VARCHAR2')
                        else:
                            output_list.append(f'{item} IN VARCHAR2')
                    output_params = ', '.join(output_list)
                    # mrd
                    method_content = "FUNCTION " + method_name + "(" + output_params + ") " + method_access
                    package_content += f"""
     {method_content};       
                                    """
                    package_body += f"""
     {method_content}IS   
     /* todo */
     BEGIN
     /* todo */ 
        RETURN NULL;  
     END {method_name};
                """

                package_end = f"""
     ----------------- END IMPLEMENTATION -------------------
END {file_convert_name};
/
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

            # convert if else :
            to_code_temp = process_code(to_code_temp)

            # Convert comment #; /// ;
            to_code_temp = convert_comment_pattern(to_code_temp)

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
            pattern_dola_dola_2 = r'\$\$([^\s(\^]+)\(([^)]+)'
            to_code_temp = convert_from_pattern_dola_dola_2(pattern_dola_dola_2, to_code_temp)

            # check Do[3] : Do MethodName^RoutineName(param, ...) -> ROUTINE_NAME_MAC.MethodName(param1, param2,...)
            pattern_do_3 = r'Do (\w+)\^(\w+)\.(\w+)\((.*?)\)'
            # Tìm các kết hợp phù hợp trong chuỗi và thực hiện chuyển đổi
            matchs_do_3 = re.findall(pattern_do_3, from_code.strip())
            for match_do_3 in matchs_do_3:
                m_do3_function = match_do_3[0]
                m_do3_package = match_do_3[1].upper()
                m_do3_routine = match_do_3[2]
                m_do3_param = match_do_3[3]
                input_str_do3 = "Do " + match_do_3[0] + "^" + match_do_3[1] + "." + match_do_3[2] + "(" + match_do_3[
                    3] + ")"
                m_do3_routine = ''.join(['_' + c if c.isupper() else c for c in m_do3_routine]).lstrip('_')
                m_do3_routine = m_do3_routine.upper()
                # kiểm tra xem param có . không, nếu có remove đi
                m_do3_param = re.sub(r'\.', '', m_do3_param)
                output_str_do_3 = m_do3_package + "_" + m_do3_routine + "_MAC." + m_do3_function + "(" + m_do3_param + ")"

                to_code_temp = to_code_temp.replace(input_str_do3, output_str_do_3)

            # check to_code có chứa tên hàm để replace:
            pattern_func = r'\$\$([A-Za-z0-9]+)\^(\w+)\.([A-Za-z0-9]+)\(([^)]+)\)'
            matchs = re.findall(pattern_func, to_code_temp.strip())

            for match in matchs:
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
    pattern3 = r'(\;)([^\n]+)'
    to_code_temp = from_code

    matchs1 = re.findall(pattern1, from_code.strip())
    for match1 in matchs1:
        input_str1 = match1[0] + match1[1]
        output_str1 = "--" + match1[1]
        to_code_temp = to_code_temp.replace(input_str1, output_str1)

    matchs2 = re.findall(pattern2, to_code_temp.strip())
    for match2 in matchs2:
        input_str2 = match2[0] + match2[1]
        output_str2 = "--" + match2[1]
        to_code_temp = to_code_temp.replace(input_str2, output_str2)

    matchs3 = re.findall(pattern3, to_code_temp.strip())
    for match3 in matchs3:
        input_str3 = match3[0] + match3[1]
        output_str3 = "--" + match3[1]
        to_code_temp = to_code_temp.replace(input_str3, output_str3)

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
    oracle_code = cache_code.strip()

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

    # check với biểu thức IF nằm trong 1 dòng và không có {}, có set:
    pattern_if_0 = r'If\s+([^\n{]+)\s*(Set)\s*([^\n]*)'
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
    if matches_if_2:
        source_code = re.sub(pattern_if_2, r'IF \1 THEN \n\t    \2 \n\tEND IF;\n', source_code, flags=re.IGNORECASE)

    code_lines = source_code.split('\n')
    for line in code_lines:
        if "}While".upper() in line.upper():
            processed_code.append(line)
            continue
        if ("IF" in line.upper() and "THEN" in line.upper()) or ("END IF;" in line.upper()):
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
        # if (re.findall(pattern3, line.strip())) and (("if".upper or "else".upper() or "elseif") not in line.upper()):
        if re.findall(pattern3, line.strip(), flags=re.IGNORECASE):
            line = re.sub(pattern3, r'', line.strip(), flags=re.IGNORECASE)
            processed_code.append(line)
            continue
        if ("If ".upper() in line.upper()) and ("ElseIf".upper() not in line.upper()):
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
            if "{" in line:
                line = line.replace("}", "")
                if "ElseIf " in line:
                    condition = (line).split("ElseIf ")[1].split("{")[0]
                elif "elseIf" in line:
                    condition = (line).split("elseIf ")[1].split("{")[0]
                else:
                    condition = (line).split("elseif ")[1].split("{")[0]
                processed_code.append(" " * (len(stack) - 1) * 4 + f"ELSIF {condition} ")
            else:
                processed_code.append(" " * len(stack) * 4 + f"ELSIF {condition} ")
            # if "}" in line:
            #     if stack:
            #         stack.pop()  # Kết thúc một cấp độ
            #     processed_code.append(" " * len(stack) * 4 + "ELSIF")
            #     stack.append(True)  # Bắt đầu một cấp độ mới
            # else:
            #     processed_code[-1] += " ELSIF"
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
    logging.info(" [end process_code ifelse]")
    return result
