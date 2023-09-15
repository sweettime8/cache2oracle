from flask import Blueprint, request, render_template, redirect, url_for, flash, Response, jsonify
import warnings
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

                    # Tìm phần tử <Description> trong phần tử <Method> hiện tại
                    description_method = methods[i].getElementsByTagName("Description").item(0)
                    if description_method:
                        # Lấy nội dung của FormalSpec
                        description_method_value = description_method.firstChild.nodeValue
                        # chuyen doi line cho java doc
                        lines = description_method_value.split('\n')
                        formatted_description = "/**\n"
                        for line in lines:
                            formatted_description += f"     * {line.strip()}\n"
                        formatted_description += "    **/"

                    else:
                        description_method_value = ""

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
                    match_quit = re.findall(r'(Q|q)uit(\s+[a-zA-Z])?', imp_value)
                    if match_quit:
                        # Kiểm tra xem "Quit" có đi kèm với khoảng trắng và sau đó là ky tu bang chu cai
                        last_match = match_quit[-1]
                        quit_command = last_match[0]  # "Q" hoặc "q"
                        letter_after_quit = last_match[1]  # Ký tự chữ sau "Quit" (nếu có)
                        check_match = re.search(r'\s+[a-zA-Z]', letter_after_quit)

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
    END {method_name};
                            """
                        else:
                            # là procedure
                            package_content += f"""
    {formatted_description}                        
    PROCEDURE {method_name}({formal_spec_value}) RETURN {return_type_value};        
                                                    """
                            package_body += f"""
    PROCEDURE {method_name}({formal_spec_value}) RETURN {return_type_value} IS  
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
                            formatted_description_query += f"     * {line.strip()}\n"
                        formatted_description_query += "    **/"

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
                        parameter_query_query_value = convert_formal_spec(parameter_query.getAttribute("value"))
                        # Tách chuỗi thành danh sách các tham số
                        parameter_query_query_value = parameter_query_query_value.split(", ")

                        # Tạo chuỗi mới với dấu xuống dòng sau mỗi tham số
                        parameter_query_query_value = ",\n         ".join(parameter_query_query_value)
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
    FUNCTION {query_name}({formal_spec_query_value}) RETURN SYS_REFCURSOR; ;    
                        """

                    package_body += f"""
    FUNCTION {query_name}({formal_spec_query_value})  RETURN SYS_REFCURSOR IS

    /* todo */
    BEGIN
    /* todo */   
    END {query_name};
                        """

                file_content = package_header + package_content + package_body + package_end

                with open(file_convert, "w", encoding="utf-8") as sql_file:
                    sql_file.write(file_content)

            return jsonify({'status': 'success', 'message': 'Check File successful!', 'data': "data"})

    except Exception as e:
        # Xảy ra lỗi
        print("error : ", e)
        logging.error(" [start_convert_cls] error : ", e)
        return jsonify({'status': 'success', 'message': 'Check File error!', 'data': e})


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
            # Xác định kiểu của tham số đầu ra
            var_in_out = "IN"
            if '&' in var_name:
                var_name = var_name.replace('&', '').strip()
                var_in_out = "OUT"

            # Tạo định dạng đầu ra cho tham số
            output_var = f"{var_name} {var_in_out} {var_type_value}"
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


@actions.route('/convert_editor', methods=['POST'])
def convert_editor():
    print("[convert_editor] : ")
    logging.info("#### [convert_by_editor] ####")
    try:
        if request.method == 'POST':
            from_code = request.form['code-editor-1']
            conversion_rules_file_path = "./config/convert_cache_to_oracle_rules.txt"
            conversion_rules = read_conversion_rules_from_file(conversion_rules_file_path)

            # check Do[3] : Do MethodName^RoutineName(param, ...) -> ROUTINE_NAME_MAC.MethodName(param1, param2,...)
            pattern_do_3 = r'Do (\w+)\^(\w+)\.(\w+)\((.*?)\)'
            # Tìm các kết hợp phù hợp trong chuỗi và thực hiện chuyển đổi
            to_code_temp = from_code
            matchs_do_3 = re.findall(pattern_do_3, from_code.strip())
            for match_do_3 in matchs_do_3:
                m_do3_function = match_do_3[0].upper()
                m_do3_package = match_do_3[1].upper()
                m_do3_routine = match_do_3[2]
                m_do3_param = match_do_3[3]
                input_str_do3 = "Do " + match_do_3[0] + "^" + match_do_3[1] + "." + match_do_3[2] + "(" + match_do_3[
                    3] + ")"
                m_do3_routine = ''.join(['_' + c if c.isupper() else c for c in m_do3_routine]).lstrip('_')
                m_do3_routine = m_do3_routine.upper()
                output_str_do_3 = m_do3_package + "_" + m_do3_routine + "_MAC_" + m_do3_function + "(" + m_do3_param + ")"

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
        logging.error(" [convert_editor] error : ", e)
        return redirect(url_for('actions.convert_code'))


def read_conversion_rules_from_file(file_path):
    with open(file_path, 'r') as file:
        conversion_rules = [line.strip().split('|||') for line in file.readlines()]
    return conversion_rules


def convert_cache_to_oracle(cache_code, conversion_rules):
    oracle_code = cache_code.strip()

    for rule in conversion_rules:
        cache_pattern, oracle_replace = rule
        oracle_code = re.sub(cache_pattern.strip(), oracle_replace.strip(), oracle_code)
    # Sử dụng regex để loại bỏ xuống dòng
    oracle_code = re.sub(r'[\r]', '', oracle_code)
    return oracle_code


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

                pattern_method = r'([\w.]+)\(([^)]*)(?<!//)\) (Public|Private)'
                # Tìm tag <Routine> và lấy nội dung CDATA bên trong
                routine_cdata = content.getElementsByTagName("Routine")[0].firstChild.data
                methods = re.findall(pattern_method, routine_cdata)

                pattern_include = r'#Include\s+(\S+)'
                # Sử dụng re.findall để tìm tất cả các #Include trong đoạn văn bản
                includes = re.findall(pattern_include, routine_cdata)
                include_list = ""
                if includes:
                    include_list += """
    /*******************************************************
     *  DECLARE INCLUDE LIST: Where constants should be
     *******************************************************/                   
    INCLUDE_LIST STRING_ARRAY := STRING_ARRAY("""
                    pattern_storage = '\.storage'
                    for include in includes:
                        if not re.search(pattern_storage, include, re.IGNORECASE):
                            include_list += f"""'{include}',"""
                    # Loại bỏ dấu "," cuối cùng và thêm dấu ");"
                    include_list = include_list[:-1] + ');'

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
     PACKAGE_NAME VARCHAR2(150) := '{file_convert_name}';
     {include_list}
     {output_constants}
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
                    method_access = method[2]
                    method_content = "FUNCTION " + method_name + "(" + method_params + ") " + method_access
                    package_content += f"""
     {method_content}       
                                    """
                    package_body += f"""
     {method_content}   
     /* todo */
     BEGIN
     /* todo */   
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
        print("error : ", e)
        logging.error(" [start_convert_cls] error : ", e)
        return jsonify({'status': 'success', 'message': 'Check File error!', 'data': e})
