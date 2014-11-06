% title = None
% rebase('base.tpl', title=title, canonical=False)

<div class="deeds">
<h2>Recent deeds</h2>
  <table>
    <tr>
      <td>created</td>
      <td>link</td>
      <td>name</td>
      <td>bundled</td>
      <td>bundle</td>
      <td>title</td></tr>
  % for deed in recent_deeds:
    <tr>
      <td>{{date(deed['created_at'])}}</td>
      <td><a href="{{deed_url(deed['b58_hash'])}}">{{deed['b58_hash']}}</a></td>
      <td>{{deed['otc_name']}}</td>
      <td>{{date(deed['bundled_at']) if deed['bundled_at'] else 'pending'}}</td>
      % if deed['bundle_address']:
      <td><a href="{{bundle_url(deed['bundle_address'])}}">{{deed['bundle_address'][:8]}}</a></td>
      % else:
      <td>n/a</td>
      % end
      <td>{{deed['title'] or ''}}</td>
    </tr>
  % end
  </table>

<p><a href="{{bundle_page_url(0,path='deeds')}}">View more deeds</a></p>
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

<p><a href="{{bundle_page_url(0)}}">View more bundles</a></p>
</div>



