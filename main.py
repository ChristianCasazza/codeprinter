# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "flask",
#     "requests",
#     "python-dotenv",
# ]
# ///
from flask import Flask, render_template, request, redirect, url_for
import os

app = Flask(__name__)

import db_setup
from db_setup import (
    add_reusable_prompt,
    get_all_reusable_prompts,
    delete_reusable_prompt,
    get_reusable_prompt,
    update_reusable_prompt,
    get_prompt_blocks,
    add_prompt_block,
    delete_prompt_block,
    update_prompt_block,
    reorder_prompt_block,
    clear_prompt_blocks,
    get_all_tags,
    add_tag,
    delete_tag,
    update_tag,
    assign_tag_to_block,
    get_tags_for_block,
    reorder_blocks,
    export_to_csv,
)

@app.before_request
def initialize():
    if not hasattr(app, 'db_initialized'):
        db_setup.init_db()
        app.db_initialized = True

@app.route('/')
def index():
    return render_template('index.html')

# -----------------------------------------------
# Prompt Builder
# -----------------------------------------------

@app.route('/builder', methods=['GET', 'POST'])
def builder():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add_block':
            new_content = request.form.get('new_content', '')
            blocks = get_prompt_blocks()
            max_order = max(block[2] for block in blocks) if blocks else 0
            add_prompt_block(new_content, max_order + 1)
            return redirect(url_for('builder'))

        elif action == 'update_block':
            block_id = request.form.get('block_id')
            content = request.form.get('content')
            update_prompt_block(block_id, content)
            return redirect(url_for('builder'))

        elif action == 'delete_block':
            block_id = request.form.get('block_id')
            delete_prompt_block(block_id)
            return redirect(url_for('builder'))

        elif action == 'move_up':
            block_id = request.form.get('block_id')
            blocks = get_prompt_blocks()
            blocks_dict = {b[0]: {'content': b[1], 'order': b[2]} for b in blocks}
            current_order = blocks_dict[int(block_id)]['order']
            for b in blocks:
                if b[2] == current_order - 1:
                    reorder_prompt_block(b[0], current_order)
                    break
            reorder_prompt_block(block_id, current_order - 1)
            return redirect(url_for('builder'))

        elif action == 'move_down':
            block_id = request.form.get('block_id')
            blocks = get_prompt_blocks()
            blocks_dict = {b[0]: {'content': b[1], 'order': b[2]} for b in blocks}
            current_order = blocks_dict[int(block_id)]['order']
            for b in blocks:
                if b[2] == current_order + 1:
                    reorder_prompt_block(b[0], current_order)
                    break
            reorder_prompt_block(block_id, current_order + 1)
            return redirect(url_for('builder'))

        elif action == 'add_reusable':
            prompt_id = request.form.get('prompt_id')
            reusable = get_reusable_prompt(prompt_id)
            if reusable:
                blocks = get_prompt_blocks()
                max_order = max(block[2] for block in blocks) if blocks else 0
                add_prompt_block(reusable[2], max_order + 1)
            return redirect(url_for('builder'))

        elif action == 'assign_tag':
            block_id = request.form.get('block_id')
            tag_id = request.form.get('tag_id')
            if tag_id:
                assign_tag_to_block(block_id, tag_id)
            return redirect(url_for('builder'))

        elif action == 'clear_blocks':
            clear_prompt_blocks()
            return redirect(url_for('builder'))

        elif action == 'reorder_block':
            block_id = request.form.get('block_id')
            new_position = request.form.get('new_order')
            try:
                new_position = int(new_position)
                reorder_blocks(int(block_id), new_position)
            except ValueError:
                pass
            return redirect(url_for('builder'))

    blocks = get_prompt_blocks()
    reusable_prompts = get_all_reusable_prompts()
    tags = get_all_tags()
    return render_template('builder.html', blocks=blocks, reusable_prompts=reusable_prompts, tags=tags, get_tags_for_block=get_tags_for_block)

# -----------------------------------------------
# Reusable Prompts Manager
# -----------------------------------------------

@app.route('/reusable', methods=['GET', 'POST'])
def reusable_prompts():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            name = request.form.get('name')
            content = request.form.get('content')
            add_reusable_prompt(name, content)
            return redirect(url_for('reusable_prompts'))
        elif action == 'delete':
            prompt_id = request.form.get('prompt_id')
            delete_reusable_prompt(prompt_id)
            return redirect(url_for('reusable_prompts'))
        elif action == 'edit':
            prompt_id = request.form.get('prompt_id')
            name = request.form.get('name')
            content = request.form.get('content')
            update_reusable_prompt(prompt_id, name, content)
            return redirect(url_for('reusable_prompts'))

    prompts = get_all_reusable_prompts()
    return render_template('reusable.html', prompts=prompts)

# -----------------------------------------------
# Tag Manager
# -----------------------------------------------

@app.route('/tags', methods=['GET', 'POST'])
def manage_tags():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            name = request.form.get('name')
            if name:
                add_tag(name)
            return redirect(url_for('manage_tags'))
        elif action == 'delete':
            tag_id = request.form.get('tag_id')
            delete_tag(tag_id)
            return redirect(url_for('manage_tags'))
        elif action == 'edit':
            tag_id = request.form.get('tag_id')
            name = request.form.get('name')
            update_tag(tag_id, name)
            return redirect(url_for('manage_tags'))

    tags = get_all_tags()
    return render_template('tags.html', tags=tags)

# -----------------------------------------------
# Export Functionality
# -----------------------------------------------

@app.route('/export', methods=['POST'])
def export():
    export_to_csv()
    return redirect(url_for('index'))

# -----------------------------------------------
# MAIN ENTRY POINT
# -----------------------------------------------
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)