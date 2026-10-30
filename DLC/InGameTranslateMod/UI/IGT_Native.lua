-- Native async transport. Never touches game RNG, game state or multiplayer
-- packets. All translation decisions/quotas belong to the remote service.
IGT_Native = {}
function IGT_Native.Open(config, query, state, session)
    local function quote(s) return "'" .. tostring(s or ""):gsub("'", "''") .. "'" end
    local function value(k)
        local rows=query("SELECT value FROM igt_state WHERE key="..quote(k))
        return rows[1] and rows[1].value
    end
    local clock, job, current, inflight = 0, nil, nil, nil
    local cache, order = {}, {}
    local sequenceKey="dlc_sequence_"..config.id
    local key=IGT_Crypto.unhex(config.key)
    local function finish(result, detected, err)
        if current then
            query("UPDATE native_requests SET status="..quote(err and 'error' or 'done')..",result="..quote(result)..",detected="..quote(detected)..",error="..quote(err).." WHERE id="..tonumber(current.id).." AND session="..quote(session))
        end
        current,job=nil,nil
    end
    local function translate(row)
        local cacheKey=row.source.."\n"..row.target.."\n"..row.text
        if cache[cacheKey] then finish(cache[cacheKey][1],cache[cacheKey][2]);return end
        if #row.text>6000 then finish(nil,nil,"Shorten the message to 6,000 UTF-8 bytes.");return end
        local seq=tonumber(value(sequenceKey) or '0')
        assert(seq and seq>=0 and seq<99999999999999,"Invalid sequence")
        seq=string.format('%.0f',seq+1)
        -- Persist before sending. A crash can skip a sequence, never reuse it.
        state(sequenceKey,seq)
        local sealed=IGT_Crypto.seal(key,{'IGT-request/v1',config.id,seq},row.source..'\n'..row.target..'\n'..row.text)
        inflight=Network.HttpRequest({url=config.url..'/v2/dlc/'..config.id..'/'..seq..'/'..IGT_Crypto.hex(sealed),verb='GET',headers={'Cache-Control: no-store','User-Agent: ImprovedChat-DLC/1'}})
        assert(inflight,"Request unavailable")
        local body,started='',clock
        repeat
            local piece=inflight:PopReceivedData()
            if type(piece)=='string' then body=body..piece end
            assert(#body<=16000 and clock-started<45,"Invalid or timed out response")
            if not inflight:Finished() then coroutine.yield() end
        until inflight:Finished()
        local last=inflight:PopReceivedData();if type(last)=='string' then body=body..last end
        inflight=nil
        assert(#body<=16000,"Response too large")
        local plain=IGT_Crypto.open(key,{'IGT-response/v1',config.id,seq,sealed:sub(1,16)},IGT_Crypto.unhex(body))
        assert(plain,"Unverified response")
        local detected,result=plain:match('^ok\n([a-z]+)\n(.*)$')
        if not result then finish(nil,nil,plain:match('^error\n(.+)$') or 'Invalid translation response.');return end
        cache[cacheKey]={result,detected};order[#order+1]=cacheKey
        if #order>500 then cache[table.remove(order,1)]=nil end
        finish(result,detected)
    end
    -- Ready on first install; preserve a user's explicit disable choice.
    local enabled=value('native_translation_consent')~='0'
    state('native_online_enabled',enabled and '1' or '0')
    local api={}
    function api.Enabled() return enabled end
    function api.Enable(value)
        enabled=value==true
        state('native_translation_consent',enabled and '1' or '0')
        state('native_online_enabled',enabled and '1' or '0')
        if not enabled then
            finish(nil,nil,'Online translation is disabled.')
            query("UPDATE native_requests SET status='error',error='Online translation is disabled.' WHERE session="..quote(session).." AND status='pending'")
        end
    end
    function api.Update(dt)
        clock=clock+dt
        if not enabled then return end
        -- Keep an expired/cancelled handle until it completes; never pile up
        -- background requests after repeated timeouts or disabling consent.
        if not job and inflight then
            inflight:PopReceivedData()
            if inflight:Finished() then inflight=nil end
            return
        end
        if not job then
            local rows=query("SELECT id,text,source,target FROM native_requests WHERE session="..quote(session).." AND status='pending' ORDER BY id LIMIT 1")
            if not rows[1] then return end
            current=rows[1]
            query("UPDATE native_requests SET status='working' WHERE id="..tonumber(current.id))
            local row=current
            job=coroutine.create(function() translate(row) end)
        end
        -- A single AES block per UI update keeps work cooperative in Lua 5.1.
        IGT_Crypto.setYield(function() coroutine.yield() end)
        local running=job
        local ok=coroutine.resume(running)
        IGT_Crypto.setYield(nil)
        if not ok then finish(nil,nil,'Cannot verify the translation service response. Check your connection and try again.')
        elseif job and coroutine.status(running)=='dead' then finish(nil,nil,'Translation did not finish.') end
    end
    return api
end
