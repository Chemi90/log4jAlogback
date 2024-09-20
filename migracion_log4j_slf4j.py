import os
import re
import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import filedialog, messagebox

def migrate_pom_xml(file_path):
    print(f"\nProcesando pom.xml: {file_path}")
    try:
        # Registrar el namespace para evitar prefijos como ns0
        ET.register_namespace('', 'http://maven.apache.org/POM/4.0.0')
        tree = ET.parse(file_path)
        root = tree.getroot()
        ns = {'maven': 'http://maven.apache.org/POM/4.0.0'}

        modified = False

        # Eliminar dependencias específicas
        dependencies_to_remove = []
        for dep in root.findall('.//maven:dependencies/maven:dependency', ns):
            group_id = dep.find('maven:groupId', ns)
            artifact_id = dep.find('maven:artifactId', ns)
            if group_id is not None and artifact_id is not None:
                if (group_id.text == 'org.slf4j' and artifact_id.text == 'slf4j-log4j12') or \
                   (group_id.text == 'log4j'):
                    dependencies_to_remove.append(dep)

        for dep in dependencies_to_remove:
            # Buscar el elemento <dependencies> padre
            dependencies_parent = dep.find('..')
            if dependencies_parent is None:
                # Buscar manualmente el padre si find('..') no funciona
                for deps in root.findall('.//maven:dependencies', ns):
                    if dep in deps:
                        dependencies_parent = deps
                        break
            if dependencies_parent is not None:
                dependencies_parent.remove(dep)
                modified = True
                print(f"  - Eliminada dependencia: {dep.find('maven:groupId', ns).text}:{dep.find('maven:artifactId', ns).text}")

        # Excluir Log4j de dependencias transitivas
        for dep in root.findall('.//maven:dependencies/maven:dependency', ns):
            exclusions = dep.find('maven:exclusions', ns)
            if exclusions is None:
                continue
            # Verificar si ya existe una exclusión para Log4j
            has_log4j_exclusion = False
            for exclusion in exclusions.findall('maven:exclusion', ns):
                ex_group_id = exclusion.find('maven:groupId', ns)
                ex_artifact_id = exclusion.find('maven:artifactId', ns)
                if ex_group_id is not None and ex_artifact_id is not None:
                    if ex_group_id.text == 'log4j':
                        has_log4j_exclusion = True
                        break
            if not has_log4j_exclusion:
                # Añadir exclusión de log4j
                exclusion = ET.SubElement(exclusions, '{http://maven.apache.org/POM/4.0.0}exclusion')
                ET.SubElement(exclusion, '{http://maven.apache.org/POM/4.0.0}groupId').text = 'log4j'
                ET.SubElement(exclusion, '{http://maven.apache.org/POM/4.0.0}artifactId').text = 'log4j'
                modified = True
                print(f"  - Añadida exclusión de log4j en dependencia: {dep.find('maven:artifactId', ns).text}")

        # Verificar si SLF4J y Logback ya están presentes
        slf4j_present = any(
            dep.find('maven:groupId', ns).text == 'org.slf4j' and dep.find('maven:artifactId', ns).text == 'slf4j-api'
            for dep in root.findall('.//maven:dependencies/maven:dependency', ns)
        )
        logback_present = any(
            dep.find('maven:groupId', ns).text == 'ch.qos.logback' and dep.find('maven:artifactId', ns).text == 'logback-classic'
            for dep in root.findall('.//maven:dependencies/maven:dependency', ns)
        )

        # Añadir SLF4J API si no está presente
        if not slf4j_present:
            add_dependency(root, ns, 'org.slf4j', 'slf4j-api', '1.7.36')
            modified = True
            print("  - Añadida dependencia: org.slf4j:slf4j-api:1.7.36")

        # Añadir Logback Classic si no está presente
        if not logback_present:
            add_dependency(root, ns, 'ch.qos.logback', 'logback-classic', '1.4.11')
            modified = True
            print("  - Añadida dependencia: ch.qos.logback:logback-classic:1.4.11")

        # Guardar los cambios solo si hubo modificaciones
        if modified:
            tree.write(file_path, encoding='utf-8', xml_declaration=True)
            print(f"  - Guardado pom.xml actualizado: {file_path}")
        else:
            print("  - No se realizaron cambios en este pom.xml.")

    except ET.ParseError as e:
        print(f"  [Error] No se pudo parsear {file_path}: {e}")
    except Exception as e:
        print(f"  [Error] Ocurrió un error al procesar {file_path}: {e}")

def add_dependency(root, ns, group_id_text, artifact_id_text, version_text):
    # Buscar o crear la sección <dependencies>
    dependencies = root.find('.//maven:dependencies', ns)
    if dependencies is None:
        # Crear <dependencies> si no existe
        dependencies = ET.SubElement(root, '{http://maven.apache.org/POM/4.0.0}dependencies')

    # Crear la nueva dependencia
    dependency = ET.SubElement(dependencies, '{http://maven.apache.org/POM/4.0.0}dependency')
    ET.SubElement(dependency, '{http://maven.apache.org/POM/4.0.0}groupId').text = group_id_text
    ET.SubElement(dependency, '{http://maven.apache.org/POM/4.0.0}artifactId').text = artifact_id_text
    ET.SubElement(dependency, '{http://maven.apache.org/POM/4.0.0}version').text = version_text

def migrate_java_file(file_path):
    print(f"Procesando archivo Java: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()

        original_content = content
        modified = False

        # Eliminar importaciones de Log4j
        new_content = re.sub(r'import\s+org\.apache\.log4j\.Logger;\s*', '', content)
        if new_content != content:
            modified = True
            print("  - Eliminadas importaciones de Log4j.")
            content = new_content

        # Añadir importaciones de SLF4J si no existen
        if not re.search(r'import\s+org\.slf4j\.Logger;', content) or not re.search(r'import\s+org\.slf4j\.LoggerFactory;', content):
            # Insertar después de los últimos import existentes
            import_statements = re.findall(r'import\s+.*?;\s*', content, re.DOTALL)
            if import_statements:
                last_import = import_statements[-1]
                slf4j_imports = "import org.slf4j.Logger;\nimport org.slf4j.LoggerFactory;\n"
                content = content.replace(last_import, last_import + "\n" + slf4j_imports)
            else:
                # Si no hay importaciones, añadir al inicio después del package
                content = re.sub(r'(package\s+[\w\.]+;\s*)', r'\1\nimport org.slf4j.Logger;\nimport org.slf4j.LoggerFactory;\n', content)
            modified = True
            print("  - Añadidas importaciones de SLF4J.")

        # Cambiar la declaración del logger
        class_name_match = re.search(r'public\s+class\s+(\w+)', content)
        if class_name_match:
            class_name = class_name_match.group(1)
            # Patrón para encontrar la declaración del logger de Log4j
            pattern = re.compile(r'private\s+static\s+Logger\s+logger\s*=\s*Logger\.getLogger\(\s*\w+\.class\s*\)\s*;')
            replacement = f'private static final Logger logger = LoggerFactory.getLogger({class_name}.class);'
            new_content, count = pattern.subn(replacement, content)
            if count > 0:
                modified = True
                print("  - Actualizada declaración del logger a SLF4J.")
                content = new_content
            else:
                # Si no se encontró la declaración del logger, agregarla después de la declaración de la clase
                logger_declaration = f'    private static final Logger logger = LoggerFactory.getLogger({class_name}.class);\n'
                new_content, count = re.subn(
                    r'(public\s+class\s+' + re.escape(class_name) + r'\s*{)',
                    r'\1\n' + logger_declaration,
                    content
                )
                if count > 0:
                    modified = True
                    print("  - Añadida declaración del logger a SLF4J.")
                    content = new_content
        else:
            print(f"  [Advertencia] No se pudo determinar el nombre de la clase en {file_path}")

        # Cambiar llamadas al logger con concatenaciones a placeholders
        new_content = re.sub(
            r'logger\.(info|debug|warn|error)\("([^"]+)"\s*\+\s*([^\)]+)\)',
            r'logger.\1("\2 {}", \3)',
            content
        )
        if new_content != content:
            modified = True
            print("  - Actualizadas llamadas al logger con concatenaciones a placeholders.")
            content = new_content

        # Cambiar logger.error(e.getStackTrace()) a logger.error("Error al procesar la solicitud", e)
        new_content = re.sub(
            r'logger\.error\(\s*([^\)]+)\.getStackTrace\(\s*\)\s*\)',
            r'logger.error("Error al procesar la solicitud", \1)',
            content
        )
        if new_content != content:
            modified = True
            print("  - Actualizada captura de excepciones en logs.")
            content = new_content

        # Reemplazar <CLASS_NAME> si fue usado
        if class_name_match:
            content = content.replace('<CLASS_NAME>', class_name_match.group(1))

        # Escribir cambios solo si hay modificaciones
        if modified:
            with open(file_path, 'w', encoding='utf-8') as file:
                file.write(content)
            print(f"  - Archivo Java modificado: {file_path}")
        else:
            print(f"  - No se realizaron cambios en: {file_path}")

    except Exception as e:
        print(f"  [Error] Procesando {file_path}: {e}")

def migrate_directory(directory):
    for root_dir, dirs, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root_dir, file)
            if file == "pom.xml":
                migrate_pom_xml(file_path)
            elif file.endswith(".java"):
                migrate_java_file(file_path)

def select_directory():
    root = tk.Tk()
    root.withdraw()  # Ocultar la ventana principal
    directory = filedialog.askdirectory(title="Selecciona el directorio raíz de tu proyecto Maven")
    return directory

def main():
    print("Migración Completa de Log4j a SLF4J con Logback - Iniciando...")
    directory = select_directory()
    if directory:
        print(f"\nDirectorio seleccionado: {directory}")
        confirm = messagebox.askyesno("Confirmar", f"¿Deseas migrar todos los archivos pom.xml y .java en:\n{directory}\n?")
        if confirm:
            migrate_directory(directory)
            messagebox.showinfo("Finalizado", "La migración ha finalizado exitosamente.")
            print("\nMigración completada exitosamente.")
        else:
            print("\nOperación cancelada por el usuario.")
    else:
        print("\nNo se seleccionó ningún directorio.")

if __name__ == "__main__":
    main()
