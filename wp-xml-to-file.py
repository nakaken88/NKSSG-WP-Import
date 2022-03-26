from pathlib import Path
import re
import shutil
import sys
from urllib.parse import quote, unquote
import xml.etree.ElementTree as ET

# how to use
# python wp-xml-to-file.py XML_PATH

ns = {}
log = []
images = {}

def wp_xml_to_file():

    if len(sys.argv) == 1:
        print('no xml path in arg')
        return

    wp_xml_path = Path(sys.argv[1])
    if wp_xml_path.suffix != '.xml':
        print('file is not xml')
        return

    xml_filename = wp_xml_path.stem
    dest_dir = Path(wp_xml_path).parent / xml_filename

    # if dest_dir.exists(): # to refresh dir
    #     shutil.rmtree(dest_dir)
    dest_dir.mkdir(exist_ok=True)


    root = ET.parse(wp_xml_path).getroot()

    for item in root.iterfind('./channel//item'):
        set_ns(item)


    res = get_all_xml_tags(root)
    dest_file = dest_dir / 'xml_tags.txt'
    dest_file.write_text('\n'.join(sorted(res)), encoding='utf-8' )


    res, site_link = get_site_info(root)
    dest_file = dest_dir / 'site_info.txt'
    dest_file.write_text('\n'.join(res), encoding='utf-8' )


    xml_main_info = get_xml_main_info(root)
    res = []
    for key in xml_main_info:
        title = '[ ' + key + ' ]\n'
        res.append(title + '\n'.join(sorted(xml_main_info[key])))

    dest_file = dest_dir / 'main_info.txt'
    dest_file.write_text('\n\n'.join(res), encoding='utf-8' )


    res = get_tax_tree(root)
    dest_file = dest_dir / 'tax_tree.txt'
    dest_file.write_text('\n'.join(res), encoding='utf-8' )


    for item in root.iterfind('./channel//item', ns):
        id = get_text(item, 'wp:post_id')
        if id == '' or not get_text(item, 'wp:post_type') in ['attachment']:
            continue
        url = get_text(item, 'wp:attachment_url')
        images[id] = url

    for item in root.iterfind('./channel//item', ns):
        save_item_to_file(item, xml_main_info, site_link, dest_dir)


    res = log
    dest_file = dest_dir / 'log.txt'
    dest_file.write_text('\n'.join(res), encoding='utf-8' )



def set_ns(item):
    for key in item:
        if not '{' in key.tag:
            continue

        url = key.tag.split('}')[0][1:]
        if 'excerpt' in url:
            ns['excerpt'] = url
        elif 'content' in url:
            ns['content'] = url
        elif 'wellformedweb' in url:
            ns['wfw'] = url
        elif 'dc' in url:
            ns['dc'] = url
        elif 'wordpress' in url:
            ns['wp'] = url

        for child in item:
            set_ns(child)

def clean_tag(tag):
    for n in ns:
        tag = tag.replace('{' + ns[n] + '}', n + ':')
    return tag

def get_text(node, key, enclose=False):
    value = node.find(key, ns)
    if value is None:
        value = ''
    else:
        value = value.text or ''
    
    if value and enclose:
        return '"' + value + '"'
    else:
        return value


def get_all_xml_tags(root):
    xml_tags = []
    for node in root.iterfind('./channel', ns):
        get_all_xml_tags_each(xml_tags, node)
    return xml_tags


def get_all_xml_tags_each(xml_tags, node):
    tag = clean_tag(node.tag)

    if not tag in xml_tags:
        xml_tags.append(tag)

    for child in node:
        get_all_xml_tags_each(xml_tags, child)



def get_site_info(root):
    title = get_text(root, './channel/title')
    link = get_text(root, './channel/link')
    desc = get_text(root, './channel/description')
    lang = get_text(root, './channel/language')

    res = ['site:']
    res.append('  site_name: "' + title + '"')
    res.append('  site_url: "' + link + '"')
    res.append('  site_desc: "' + desc + '"')
    res.append('  language: "' + lang + '"')
    return res, link



def get_xml_main_info(root):
    xml_main_info = {
        'post_type': [],
        'category': [],
        'meta': [],
        }

    for node in root.iterfind('./channel//item', ns):
        get_xml_main_info_each(xml_main_info, node)

    return xml_main_info


def get_xml_main_info_each(xml_main_info, node):
    tag = clean_tag(node.tag)

    if tag == 'wp:post_type':
        post_type = node.text
        if not post_type in xml_main_info['post_type']:
            xml_main_info['post_type'].append(post_type)

    if tag == 'category':
        category = node.attrib.get('domain')
        if not category is None and not category in xml_main_info['category']:
            xml_main_info['category'].append(category)

    if tag == 'wp:meta_key':
        meta_key = node.text
        if not meta_key in xml_main_info['meta']:
            xml_main_info['meta'].append(meta_key)

    for child in node:
        get_xml_main_info_each(xml_main_info, child)



def get_tax_tree(root):

    tax_items = {}
    tax_slugs = {}
    slug_to_names = {}

    for node in root.iterfind('./channel/wp:category', ns):
        
        taxonomy = 'category'
        item = {
            'slug': unquote(get_text(node, 'wp:category_nicename')),
            'name': get_text(node, 'wp:cat_name'),
            'parent': get_text(node, 'wp:category_parent'),
            'desc': get_text(node, 'wp:category_description'),
        }
        if tax_items.get(taxonomy) is None:
            tax_items[taxonomy] = []
            tax_slugs[taxonomy] = []
            slug_to_names[taxonomy] = {}

        if not item['slug'] in tax_slugs[taxonomy]:
            tax_items[taxonomy].append(item)
            tax_slugs[taxonomy].append(item['slug'])
            slug_to_names[taxonomy][item['slug']] = item['name']


    for node in root.iterfind('./channel/wp:tag', ns):
        
        taxonomy = 'tag'
        item = {
            'slug': unquote(get_text(node, 'wp:tag_slug')),
            'name': get_text(node, 'wp:tag_name'),
            'desc': get_text(node, 'wp:tag_description'),
        }

        if tax_items.get(taxonomy) is None:
            tax_items[taxonomy] = []
            tax_slugs[taxonomy] = []
            slug_to_names[taxonomy] = {}

        if not item['slug'] in tax_slugs[taxonomy]:
            tax_items[taxonomy].append(item)
            tax_slugs[taxonomy].append(item['slug'])
            slug_to_names[taxonomy][item['slug']] = item['name']


    for node in root.iterfind('./channel/wp:term', ns):
        
        taxonomy = get_text(node, 'wp:term_taxonomy')
        if taxonomy in ['nav_menu']:
            continue

        if taxonomy == 'post_tag':
            taxonomy = 'tag'

        item = {
            'slug': unquote(get_text(node, 'wp:term_slug')),
            'name': get_text(node, 'wp:term_name'),
            'parent': get_text(node, 'wp:term_parent'),
            'desc': get_text(node, 'wp:term_description'),
        }

        if tax_items.get(taxonomy) is None:
            tax_items[taxonomy] = []
            tax_slugs[taxonomy] = []
            slug_to_names[taxonomy] = {}

        if not item['slug'] in tax_slugs[taxonomy]:
            tax_items[taxonomy].append(item)
            tax_slugs[taxonomy].append(item['slug'])
            slug_to_names[taxonomy][item['slug']] = item['name']


    res = ['taxonomy: ']
    for taxonomy in tax_items:
        if taxonomy == 'post_tag':
            res.append('  - tag: ')
        else:
            res.append('  - ' + taxonomy + ': ')

        for item in tax_items[taxonomy]:
            temp = []

            for key, value in item.items():
                if value is None or value == '':
                    continue
                elif key == 'name':
                    continue
                elif key == 'slug' and item['name'].lower() != value.lower():
                    temp.append('        ' + key + ': ' + value)
                elif key == 'parent':
                    parent = slug_to_names[taxonomy][unquote(value)]
                    temp.append('        ' + key + ': ' + parent)
                elif key == 'desc':
                    temp.append('        ' + key + ': ' + value)

            if temp:
                res.append('    - ' + item['name'] + ': ')
                for v in temp:
                    res.append(v)
            else:
                res.append('    - ' + item['name'])
    return res



def save_item_to_file(item, xml_main_info, site_link, dest_dir):

    id = get_text(item, 'wp:post_id')
    title = get_text(item, 'title')

    if get_text(item, 'wp:post_type') in ['attachment']:
        log.append('ID: ' + id + ' pass(attachment) ' + title)
        return


    texts = ['---']
    texts.append('title: "' + title.replace('"', '&quot;') + '"')

    link = get_text(item, 'link')
    if link != '':
        texts.append('link: "' + link + '"')
        if not '?' in link:
            texts.append('url: "' + link.replace(site_link, '') + '"')

    if get_text(item, 'description'):
        texts.append('description: "' + get_text(item, 'description') + '"')

    if get_text(item, 'wp:post_date'):
        texts.append('date: ' + get_text(item, 'wp:post_date'))

    if get_text(item, 'wp:post_type'):
        texts.append('post_type: "' + get_text(item, 'wp:post_type') + '"')

    if get_text(item, 'wp:status'):
        texts.append('status: "' + get_text(item, 'wp:status') + '"')

    if get_text(item, 'wp:menu_order'):
        texts.append('order: ' + get_text(item, 'wp:menu_order'))


    metas = {}
    for category in item.iterfind('./category', ns):
        domain = category.attrib['domain']
        if domain == 'post_tag':
            domain = 'tag'
        if metas.get(domain) is None:
            metas[domain] = []

        value = category.text.replace('"', "'")
        if not value:
            continue
        elif value.isdecimal():
            metas[domain].append(value)
        else:
            metas[domain].append('"' + value + '"')

    image_flag = True
    for meta in item.iterfind('./wp:postmeta', ns):
        key = get_text(meta, 'wp:meta_key')
        value = get_text(meta, 'wp:meta_value')
        
        if key == '_thumbnail_id' and image_flag:
            if value in images.keys():
                texts.append('image: \n  src: ' + images[value])
                image_flag = False
                continue
        if not value:
            continue
        elif key[0] == '_':
            continue
        elif key == 'post_tag':
            key = 'tag'
        if metas.get(key) is None:
            metas[key] = []

        value = value.replace('"', "'")
        if value.isdecimal():
            metas[key].append(value)
        else:
            metas[key].append('"' + value + '"')

    meta_list = []
    for meta in metas:
        join_categories = '[' + ', '.join(metas[meta]) + ']'
        meta_list.append(meta + ': ' + join_categories)
    
    if meta_list:
        texts.append('\n'.join(meta_list))

    texts.append('---')

    if get_text(item, 'content:encoded'):
        content = get_text(item, 'content:encoded')
        texts.append(content)


    post_date = get_text(item, 'wp:post_date')

    filename = post_date.replace('-', '').replace(':', '').replace(' ', '-')
    if id == '':
        filename = filename + '-' + title[:100] + '.txt'
    else:
        filename = filename + '-' + str(id) + '.txt'

    folder = post_date.split(' ')[0].split('-')[:2]
    status = get_text(item, 'wp:status')

    if status in ['draft', 'future', 'pending', 'private', 'trash', 'auto-draft', 'inherit']:
        dir = Path(dest_dir, status, *folder)
    else:
        dir = Path(dest_dir, get_text(item, 'wp:post_type'), *folder)

    dir.mkdir(parents=True, exist_ok=True)

    path = dir / filename
    path.write_text( '\n'.join(texts), encoding='utf-8' )
    
    if id == '':
        memo = 'pubDate: ' + get_text(item, 'pubDate')
    else:
        memo = 'ID: ' + id

    log.append(memo + ' ' + str(path.relative_to(dest_dir)))



if __name__ == '__main__':
    wp_xml_to_file()