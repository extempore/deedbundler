% title = None
% rebase('base.tpl', title=title, canonical=False)

<div class="deeds">
<h2>Pending deeds</h2>
% if pending_deeds:
  <table>
    <tr><td>created</td><td>link</td><td>name</td><td>title</td></tr>
  % for deed in pending_deeds:
    <tr>
      <td>{{date(deed['created_at'])}}</td>
      <td><a href="{{deed_url(deed['b58_hash'])}}">{{deed['b58_hash']}}</a></td>
      <td>{{deed['otc_name']}}</td>
      <td>{{deed['title'] or ''}}</td>
    </tr>
  % end
  </table>
% else:
<p>No deeds pending</p>
% end
</div>

<div class="bundles">
<h2>Recent bundles</h2>
  <table>
    <tr>
      <td>created</td>
      <td>link</td>
      <td>deeds</td>
      <td>confirmed</td>
      <td>tx</td>
    </tr>
  % for bundle in recent_bundles:
    <tr>
      <td>{{date(bundle['created_at'])}}</td>
      <td><a href="{{bundle_url(bundle['address'])}}">{{bundle['address']}}</a></td>
      <td>{{bundle['num_deeds']}}</td>
    % conf = bundle['confirmed_at']
      <td>{{date(conf) if conf else 'n/a'}}</td>
      <td>(<a href="https://blockchain.info/tx/{{bundle['txid']}}">tx</a>)</td>
    </tr>
  % end
  </table>

<p><a href="{{bundle_page_url(0)}}">View more</a></p>
</div>

