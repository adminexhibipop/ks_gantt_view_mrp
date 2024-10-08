/** @odoo-module **/

import {ksGanttRenderer} from "@ks_gantt_view_base/js/ks_gantt_renderer_new";
import { patch } from "@web/core/utils/patch";
import { jsonrpc } from "@web/core/network/rpc_service";

patch(ksGanttRenderer.prototype,{
    willstart(){
             var ks_def;
      var ks_super = super.willstart();
      if (this.ks_model_name == "mrp.production") {
        ks_def = jsonrpc("/web/dataset/call_kw",{
          model: "mrp.gantt.settings",
          method: "ks_get_gantt_view_mrp_settings",
          args: [],
          kwargs:{}
        }).then(
          function (result) {
            this.ks_enable_task_dynamic_text =
              result.ks_enable_task_dynamic_text;
            this.ks_enable_task_dynamic_progress = false;
            this.ks_enable_quickinfo_extension =
              result.ks_enable_quickinfo_extension;
            this.ks_project_tooltip_config = result.ks_project_tooltip_config
              ? result.ks_project_tooltip_config
              : false;
          }.bind(this)
        );
      } else if (this.ks_model_name == "mrp.workorder") {
        ks_def = jsonrpc("/web/dataset/call_kw",{
          model: "mrp.gantt.settings",
          method: "ks_get_gantt_view_mrp_settings_wo",
          args: [],
          kwargs:{}
        }).then(
          function (result) {
            this.ks_enable_task_dynamic_text =
              result.ks_enable_task_dynamic_text;
            this.ks_enable_task_dynamic_progress =
              result.ks_enable_task_dynamic_progress;
            this.ks_enable_quickinfo_extension =
              result.ks_enable_quickinfo_extension;
            this.ks_project_tooltip_config = result.ks_project_tooltip_config
              ? result.ks_project_tooltip_config
              : false;
          }.bind(this)
        );
      }
      return Promise.all([ks_def, ks_super]);
    },

    });

